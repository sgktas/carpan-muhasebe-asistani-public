from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime as _datetime_cls
from itertools import combinations
import re

from app.models.records import BankStatementRecord, NetsisReportRecord

_MIN_DATE = _datetime_cls.min
AMOUNT_TOLERANCE_CENTS = 0  # kuruşuna kadar tutmalı; tolerans gerçek hataları gizler
MAX_SUBSET_SEARCH_CANDIDATES = 20  # asiri kombinasyon aramasini onler (subeli_matcher ile ayni sinir)

# Banka açıklamalarında sıkça geçen, şirket adını AYIRT ETMEYEN referans/kurumsal
# ek kelimeler. Bunlar "önemli kelime" sayılmaz; aksi halde iki farklı şirketin
# ortak "SANAYİ TİCARET LİMİTED" gibi ekleri paylaşması yanlışlıkla eşleşmeye
# yol açabilir. Yeni bir kalıp fark edilirse buraya eklenmesi yeterli.
_DESCRIPTION_STOPWORDS = {
    "FAST", "HAVALE", "CEP", "SUBE", "HVL", "EF", "INT", "BAT", "CARI", "MOBIL",
    "SANAYI", "TICARET", "TICARI", "LIMITED", "SIRKETI", "ANONIM", "TURIZM",
    "INSAAT", "ITHALAT", "IHRACAT", "ITH", "IHR", "PETROL", "MARKET", "OTOMOTIV",
    "TEKSTIL", "ILETISIM", "SORUMLU", "SINIRLI", "ISCI", "EMEK", "TUKETIM",
    "KOOPERATIFI", "URUNLERI", "GIDA", "VE", "SAN", "TIC", "LTD", "STI",
}
_MIN_SIGNIFICANT_WORD_LENGTH = 4
_MIN_DISTINCTIVE_WORD_LENGTH = 7  # tek kelimeyle eslesmeye yetecek kadar ayirt edici
_TURKISH_UPPER_MAP = {"Ş": "S", "Ğ": "G", "Ü": "U", "Ö": "O", "Ç": "C"}


@dataclass(frozen=True)
class ReconciliationResult:
    banka_bakiyesi: float | None
    netsis_bakiyesi: float | None
    fark: float | None
    mutabik: bool
    eslesen_sayisi: int
    bolunmus_grup_sayisi: int = 0
    sadece_bankada: list[BankStatementRecord] = field(default_factory=list)
    sadece_netposte: list[NetsisReportRecord] = field(default_factory=list)


class ReconciliationEngine:
    """Banka ekstresi ile Netsis ay sonu raporunu karşılaştırır.

    Üç aşamalı eşleştirme yapılır:

    1) Birebir eşleştirme: aynı tarih + aynı tutar.

    2) Bölünmüş fiş eşleştirmesi (açıklama bazlı): MANİM Aktarma modülündeki
       "Şubeliler" kayıtlarıyla aynı gerçek dünya durumu — tek bir banka
       kaydı Netsis'te birden fazla satıra bölünmüş olabilir (veya tam
       tersi). Açıklamalar birebir aynı olmayabilir (Netsis kesebilir, FAST/
       HAVALE gibi farklı önekler kullanılabilir), bu yüzden açıklamadaki
       "önemli kelimeler" (şirket adı gibi ayırt edici kelimeler; FAST/
       HAVALE/SANAYİ/TİCARET gibi genel ekler hariç) karşılaştırılır.

    3) Bölünmüş fiş eşleştirmesi (tutar bazlı yedek): açıklamadan hiçbir
       ortak kelime bulunamayan durumlarda, aynı gün içindeki kalan
       kayıtlardan tutarları toplamda birebir tutan tekil bir alt küme
       aranır (Modül 01'deki alt küme toplamı mantığıyla aynı). Yalnızca
       TEK bir kombinasyon tutarlıysa eşleştirilir; birden fazla olası
       kombinasyon varsa belirsizlik riski nedeniyle eşleştirilmez.

    Bakiye karşılaştırması tarih/saat bakımından en yeni kaydın kümülatif
    bakiyesi üzerinden yapılır. Bazı MANİM raporları en yeni hareketi üstte
    verdiği için yalnız dosyadaki son satıra güvenilmez. Aynı tarih/saatteki
    kayıtlarda dosya sırası korunur.
    """

    ROUNDING = 2

    def reconcile(
        self,
        bank_records: list[BankStatementRecord],
        netsis_records: list[NetsisReportRecord],
    ) -> ReconciliationResult:
        bank_by_key: dict[tuple, list[BankStatementRecord]] = {}
        for record in bank_records:
            key = self._key(record.tarih, record.tutar)
            bank_by_key.setdefault(key, []).append(record)

        netsis_by_key: dict[tuple, list[NetsisReportRecord]] = {}
        for record in netsis_records:
            key = self._key(record.tarih, record.tutar)
            netsis_by_key.setdefault(key, []).append(record)

        matched_count = 0
        sadece_bankada: list[BankStatementRecord] = []
        sadece_netposte: list[NetsisReportRecord] = []

        all_keys = set(bank_by_key) | set(netsis_by_key)
        for key in all_keys:
            bank_group = bank_by_key.get(key, [])
            netsis_group = netsis_by_key.get(key, [])
            common = min(len(bank_group), len(netsis_group))
            matched_count += common
            if len(bank_group) > common:
                sadece_bankada.extend(bank_group[common:])
            if len(netsis_group) > common:
                sadece_netposte.extend(netsis_group[common:])

        # 2. asama: aciklama bazli bolunmus fis eslestirmesi.
        sadece_bankada, sadece_netposte, grup_1, eslesen_1 = self._match_by_description(
            sadece_bankada, sadece_netposte
        )
        # 3. asama: aciklamadan bulunamayanlar icin tutar bazli yedek eslestirme.
        sadece_bankada, sadece_netposte, grup_2, eslesen_2 = self._match_by_amount_subset(
            sadece_bankada, sadece_netposte
        )
        bolunmus_grup_sayisi = grup_1 + grup_2
        matched_count += eslesen_1 + eslesen_2

        sadece_bankada.sort(key=lambda r: (r.tarih or _MIN_DATE, r.kaynak_satir))
        sadece_netposte.sort(key=lambda r: (r.tarih or _MIN_DATE, r.kaynak_satir))

        banka_bakiyesi = self._closing_balance(bank_records)
        netsis_bakiyesi = self._closing_balance(netsis_records)

        fark = None
        mutabik = False
        if banka_bakiyesi is not None and netsis_bakiyesi is not None:
            fark = round(banka_bakiyesi - netsis_bakiyesi, self.ROUNDING)
            mutabik = fark == 0

        return ReconciliationResult(
            banka_bakiyesi=banka_bakiyesi,
            netsis_bakiyesi=netsis_bakiyesi,
            fark=fark,
            mutabik=mutabik,
            eslesen_sayisi=matched_count,
            bolunmus_grup_sayisi=bolunmus_grup_sayisi,
            sadece_bankada=sadece_bankada,
            sadece_netposte=sadece_netposte,
        )

    @staticmethod
    def _closing_balance(records: list) -> float | None:
        if not records:
            return None
        _, closing_record = max(
            enumerate(records),
            key=lambda item: (item[1].tarih or _MIN_DATE, item[0]),
        )
        return closing_record.bakiye

    # ------------------------------------------------------------------ #
    # 2. asama: aciklama bazli (onemli kelime ortusmesi) eslestirme
    # ------------------------------------------------------------------ #
    def _match_by_description(
        self,
        sadece_bankada: list[BankStatementRecord],
        sadece_netposte: list[NetsisReportRecord],
    ) -> tuple[list[BankStatementRecord], list[NetsisReportRecord], int, int]:
        bank_by_date: dict = defaultdict(list)
        for record in sadece_bankada:
            bank_by_date[record.tarih.date() if record.tarih else None].append(record)

        netsis_by_date: dict = defaultdict(list)
        for record in sadece_netposte:
            netsis_by_date[record.tarih.date() if record.tarih else None].append(record)

        matched_bank_ids: set[int] = set()
        matched_netsis_ids: set[int] = set()
        grup_sayisi = 0
        eslesen_toplam = 0

        for gun in set(bank_by_date) & set(netsis_by_date):
            if gun is None:
                continue
            for anchor in bank_by_date[gun]:
                if id(anchor) in matched_bank_ids:
                    continue
                candidates = [
                    r for r in netsis_by_date[gun]
                    if id(r) not in matched_netsis_ids and self._descriptions_overlap(anchor.aciklama, r.aciklama)
                ]
                if len(candidates) < 2:
                    continue
                if self._sums_reconcile(anchor.tutar, [c.tutar for c in candidates]):
                    matched_bank_ids.add(id(anchor))
                    matched_netsis_ids.update(id(r) for r in candidates)
                    grup_sayisi += 1
                    eslesen_toplam += 1 + len(candidates)

            for anchor in netsis_by_date[gun]:
                if id(anchor) in matched_netsis_ids:
                    continue
                candidates = [
                    r for r in bank_by_date[gun]
                    if id(r) not in matched_bank_ids and self._descriptions_overlap(anchor.aciklama, r.aciklama)
                ]
                if len(candidates) < 2:
                    continue
                if self._sums_reconcile(anchor.tutar, [c.tutar for c in candidates]):
                    matched_netsis_ids.add(id(anchor))
                    matched_bank_ids.update(id(r) for r in candidates)
                    grup_sayisi += 1
                    eslesen_toplam += 1 + len(candidates)

        kalan_bankada = [r for r in sadece_bankada if id(r) not in matched_bank_ids]
        kalan_netposte = [r for r in sadece_netposte if id(r) not in matched_netsis_ids]
        return kalan_bankada, kalan_netposte, grup_sayisi, eslesen_toplam

    # ------------------------------------------------------------------ #
    # 3. asama: tutar bazli yedek (alt kume toplami) eslestirme
    # ------------------------------------------------------------------ #
    def _match_by_amount_subset(
        self,
        sadece_bankada: list[BankStatementRecord],
        sadece_netposte: list[NetsisReportRecord],
    ) -> tuple[list[BankStatementRecord], list[NetsisReportRecord], int, int]:
        bank_by_date: dict = defaultdict(list)
        for record in sadece_bankada:
            bank_by_date[record.tarih.date() if record.tarih else None].append(record)

        netsis_by_date: dict = defaultdict(list)
        for record in sadece_netposte:
            netsis_by_date[record.tarih.date() if record.tarih else None].append(record)

        matched_bank_ids: set[int] = set()
        matched_netsis_ids: set[int] = set()
        grup_sayisi = 0
        eslesen_toplam = 0

        for gun in set(bank_by_date) & set(netsis_by_date):
            if gun is None:
                continue
            for anchor in bank_by_date[gun]:
                if id(anchor) in matched_bank_ids:
                    continue
                pool = [r for r in netsis_by_date[gun] if id(r) not in matched_netsis_ids]
                subset = self._find_unique_reconciling_subset(anchor.tutar, pool)
                if subset:
                    matched_bank_ids.add(id(anchor))
                    matched_netsis_ids.update(id(r) for r in subset)
                    grup_sayisi += 1
                    eslesen_toplam += 1 + len(subset)

            for anchor in netsis_by_date[gun]:
                if id(anchor) in matched_netsis_ids:
                    continue
                pool = [r for r in bank_by_date[gun] if id(r) not in matched_bank_ids]
                subset = self._find_unique_reconciling_subset(anchor.tutar, pool)
                if subset:
                    matched_netsis_ids.add(id(anchor))
                    matched_bank_ids.update(id(r) for r in subset)
                    grup_sayisi += 1
                    eslesen_toplam += 1 + len(subset)

        kalan_bankada = [r for r in sadece_bankada if id(r) not in matched_bank_ids]
        kalan_netposte = [r for r in sadece_netposte if id(r) not in matched_netsis_ids]
        return kalan_bankada, kalan_netposte, grup_sayisi, eslesen_toplam

    @classmethod
    def _find_unique_reconciling_subset(cls, amount: float, pool: list) -> list | None:
        """Havuzdaki kayıtlardan, toplamı ``amount``'a eşit olan TEK bir alt
        küme varsa döner; hiç yoksa ya da birden fazla olası kombinasyon
        varsa (belirsiz) ``None`` döner. Aşırı kombinasyon aramasını önlemek
        için havuz boyutu sınırlıdır.
        """
        if len(pool) < 2 or len(pool) > MAX_SUBSET_SEARCH_CANDIDATES:
            return None
        found: list | None = None
        for size in range(2, len(pool) + 1):
            for combo in combinations(pool, size):
                if cls._sums_reconcile(amount, [r.tutar for r in combo]):
                    if found is not None:
                        return None  # birden fazla olasi kombinasyon -> belirsiz
                    found = list(combo)
            if found is not None:
                return found
        return found

    @staticmethod
    def _sums_reconcile(amount: float, values: list[float]) -> bool:
        target_cents = round(amount * 100)
        total_cents = sum(round(v * 100) for v in values)
        return abs(total_cents - target_cents) <= AMOUNT_TOLERANCE_CENTS

    def _key(self, tarih, tutar) -> tuple:
        gun = tarih.date() if tarih else None
        return (gun, round(tutar, self.ROUNDING))

    @classmethod
    def _significant_words(cls, aciklama: str) -> set[str]:
        text = (aciklama or "").upper()
        for tr_char, ascii_char in _TURKISH_UPPER_MAP.items():
            text = text.replace(tr_char, ascii_char)
        text = text.replace("İ", "I")
        words = re.findall(r"[A-Z]+", text)
        return {
            w for w in words
            if len(w) >= _MIN_SIGNIFICANT_WORD_LENGTH and w not in _DESCRIPTION_STOPWORDS
        }

    @classmethod
    def _descriptions_overlap(cls, a: str, b: str) -> bool:
        """Netsis açıklama alanı kesilebiliyor ve FAST/HAVALE gibi önekler
        farklı olabiliyor; bu yüzden birebir metin eşleşmesi yerine, şirket
        adını oluşturan 'önemli kelimeler' karşılaştırılır. Yanlışlıkla genel
        şirket eklerinin (SANAYİ, TİCARET, LİMİTED vb.) eşleşmeyi tetiklememesi
        için bu kelimeler zaten önemli-kelime kümesinden çıkarılmıştır.
        """
        words_a = cls._significant_words(a)
        words_b = cls._significant_words(b)
        shared = words_a & words_b
        if len(shared) >= 2:
            return True
        if len(shared) == 1 and len(next(iter(shared))) >= _MIN_DISTINCTIVE_WORD_LENGTH:
            return True
        return False
