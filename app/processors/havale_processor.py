from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re

from app.core.mapping_store import MappingStore
from app.core.subeli_matcher import SubeliMatcher
from app.models.records import CustomerRecord, ManimRecord, NetsisRecord, TahsilatRecord


class HavaleProcessor:
    ACCEPTED_STATUSES = {"AKTARILDI", "OTOMATIK OLARAK AKTARILDI", "OTOMATİK OLARAK AKTARILDI"}

    def __init__(
        self,
        tahsilat_records: list[TahsilatRecord],
        customers: list[CustomerRecord],
        mapping_store: MappingStore | None = None,
        region_branch_aliases: dict[str, tuple[str, ...]] | None = None,
    ):
        self.tahsilat_records = tahsilat_records
        self.customers = customers
        self.subeli_matcher = SubeliMatcher(
            tahsilat_records,
            customers,
            mapping_store,
            region_branch_aliases=region_branch_aliases,
        )
        self.customers_by_code = {
            self._code_key(row.cari_kodu): row
            for row in customers
            if self._code_key(row.cari_kodu)
        }

    def process(self, record: ManimRecord, region: str) -> tuple[list[NetsisRecord], str | None]:
        if self._is_non_havale_status(record.dekont_durumu):
            return [], "Dekont durumu havale aktarımına uygun değil"

        if record.karsi_hesap_kodu:
            canonical = self.customers_by_code.get(self._code_key(record.karsi_hesap_kodu))
            code = canonical.cari_kodu if canonical else str(record.karsi_hesap_kodu).strip()
            return [self._netsis_record(record, code, record.tutar, "MANIM_KOD")], None

        # Açıklamadaki açık veya maskeli cari kod en kesin kimliktir.
        code_in_description = self._find_customer_code_in_description(record.aciklama)
        if code_in_description:
            customer = self.customers_by_code[code_in_description]
            return [self._netsis_record(record, customer.cari_kodu, record.tutar, "ACIKLAMA_KODU")], None

        # Şubeli kayıt: isim -> vergi/T.C. no -> tahsilat tutar mutabakatı.
        branch_rows = self.subeli_matcher.match(record, region)
        if branch_rows:
            branch_rows = self._balance_one_cent_difference(record.tutar, branch_rows)
            return [
                self._netsis_record(record, row.musteri_kodu, row.tutar, "SUBELI_TAHSILAT")
                for row in branch_rows
            ], None

        return [], (
            self.subeli_matcher.last_failure_reason
            or "İsim, vergi/T.C. no veya açıklamadaki cari kod üzerinden güvenli eşleşme bulunamadı"
        )


    @staticmethod
    def _balance_one_cent_difference(
        target_amount: float,
        rows: list[TahsilatRecord],
    ) -> list[TahsilatRecord]:
        """1 kuruşluk rapor yuvarlamasını Netsis toplamında dengeler.

        Eşleştirme motoru yalnız en fazla 1 kuruş farkı kabul eder. Kabul edilen
        fark varsa en yüksek tutarlı satıra yansıtılır; böylece üretilen Netsis
        satırlarının toplamı banka hareketiyle birebir aynı kalır.
        """
        if not rows:
            return rows

        cent = Decimal("0.01")
        target = Decimal(str(target_amount)).quantize(cent, rounding=ROUND_HALF_UP)
        total = sum(
            (Decimal(str(row.tutar)).quantize(cent, rounding=ROUND_HALF_UP) for row in rows),
            Decimal("0.00"),
        )
        difference = target - total
        if difference == 0:
            return rows
        if abs(difference) > cent:
            return rows

        largest_index = max(range(len(rows)), key=lambda index: float(rows[index].tutar))
        balanced: list[TahsilatRecord] = []
        for index, row in enumerate(rows):
            amount = Decimal(str(row.tutar)).quantize(cent, rounding=ROUND_HALF_UP)
            if index == largest_index:
                amount += difference
            balanced.append(TahsilatRecord(
                musteri_kodu=row.musteri_kodu,
                musteri_ismi=row.musteri_ismi,
                belge_tarihi=row.belge_tarihi,
                tutar=float(amount),
            ))
        return balanced

    def _find_customer_code_in_description(self, description: str) -> str | None:
        text = str(description or "").upper()
        plain_tokens = re.findall(r"(?<!\w)[A-Z0-9]{6,}(?!\w)", text)

        # Önce gerçek/düz kodu ara. Böylece cari kodun kendi içinde gerçek bir X
        # harfi varsa X ayırıcı sanılıp bozulmaz.
        exact_matches = {
            key
            for token in plain_tokens
            if (key := self._code_key(token)) in self.customers_by_code
        }
        if len(exact_matches) == 1:
            return next(iter(exact_matches))
        if len(exact_matches) > 1:
            return None

        # Bankalar cari kodu 128*12547567 veya 124-831212757 biçiminde
        # maskeleyebiliyor/ayırabiliyor. Bileşik biçimleri düz tokenlardan önce
        # çözmek gerekir; aksi halde maskeli kodun yalnızca son parçası yanlışlıkla
        # bağımsız müşteri kodu sanılabilir.
        #
        # ÖNEMLİ: (?<!\w) / (?!\w) sınır koruması olmadan, açıklamadaki Türkçe
        # harfler (İ, Ş, Ğ, Ö, Ü, Ç) [A-Z0-9] kümesinin dışında kaldığı için
        # regex yanlışlıkla önceki kelimenin son harflerini de kodun başına
        # yapıştırıyordu (örn. "TESLİMATI-128416*213022" -> "MATI-128416*213022").
        # Bu, gerçek kodu asla bulamayan sessiz bir eşleşme kaybına yol açıyordu.
        compound_matches: set[str] = set()
        raw_tokens = re.findall(r"(?<!\w)[A-Z0-9]+(?:[*/-]+[A-Z0-9]+)+(?!\w)", text)
        for raw in raw_tokens:
            compact = self._code_key(raw)
            if compact in self.customers_by_code:
                compound_matches.add(compact)

            if "*" not in raw:
                continue
            parts = [self._code_key(part) for part in re.split(r"\*+", raw)]
            parts = [part for part in parts if part]
            if len(parts) < 2:
                continue

            # Her yıldız kümesi sıfır veya daha fazla maskeli karakteri temsil
            # edebilir. Sıfır karakter desteği, yıldızın ayırıcı olarak kullanıldığı
            # banka formatlarını da kapsar. Tekil sonuç olmadan otomatik karar yok.
            pattern = re.compile("^" + ".*".join(re.escape(part) for part in parts) + "$")
            for code_key in self.customers_by_code:
                if pattern.fullmatch(code_key):
                    compound_matches.add(code_key)

        if len(compound_matches) == 1:
            return next(iter(compound_matches))
        if len(compound_matches) > 1:
            return None

        # Bazı banka açıklamalarında yıldız yerine X karakteri ayırıcı olarak
        # yazılıyor: M*11111111111 -> MX11111111111 veya D10*1111111 ->
        # D10X4841228. Token en az beş rakam içermeli; önce yalnız X'ler
        # kaldırılarak müşteri ana listesinde birebir karşılık aranır. Birebir
        # sonuç yoksa X yıldız gibi maskeli bölüm kabul edilir. Tekil sonuç
        # olmadan otomatik eşleştirme yapılmaz.
        x_separator_matches: set[str] = set()
        for token in plain_tokens:
            if "X" not in token or sum(char.isdigit() for char in token) < 5:
                continue

            collapsed = self._code_key(token.replace("X", ""))
            if collapsed in self.customers_by_code:
                x_separator_matches.add(collapsed)
                continue

            parts = [self._code_key(part) for part in re.split(r"X+", token)]
            parts = [part for part in parts if part]
            if len(parts) < 2:
                continue
            pattern = re.compile("^" + ".*".join(re.escape(part) for part in parts) + "$")
            for code_key in self.customers_by_code:
                if pattern.fullmatch(code_key):
                    x_separator_matches.add(code_key)

        return next(iter(x_separator_matches)) if len(x_separator_matches) == 1 else None

    def _netsis_record(self, source: ManimRecord, customer_code: str, amount: float, source_type: str) -> NetsisRecord:
        return NetsisRecord(
            islem_tarihi=source.islem_tarihi,
            cari_kodu=str(customer_code).strip(),
            tutar=float(amount),
            aciklama=source.aciklama,
            banka=source.banka,
            bolge="",
            kaynak=source_type,
        )

    @classmethod
    def _is_non_havale_status(cls, status: str) -> bool:
        normalized = cls._normalize_status(status)
        return bool(normalized) and normalized not in cls.ACCEPTED_STATUSES

    @staticmethod
    def _code_key(value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())

    @staticmethod
    def _normalize_status(value: str) -> str:
        return " ".join(str(value).upper().split())
