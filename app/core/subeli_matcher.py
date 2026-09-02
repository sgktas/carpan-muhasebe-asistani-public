from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import unicodedata

from app.core.mapping_store import MappingStore
from app.models.records import CustomerRecord, ManimRecord, TahsilatRecord

# Alt-küme taraması bu sınırın üzerinde patlayıcı büyür. Çoğu şubeli kayıtta
# bölgesel adayların tamamı hedef tutarı verir; alt-küme yalnız istisna akışıdır.
MAX_SUBSET_SEARCH_CANDIDATES = 20


class SubeliMatcher:
    """Şubeli banka hareketini müşteri ana listesi ve tahsilat raporuyla eşleştirir.

    Kesin iş kuralı:
      1. Önceden kaydedilmiş kullanıcı eşleştirmesi
      2. Açıklamadaki VKN/TCKN -> müşteri listesi -> işlem bölgesi
      3. Bölgesel müşteri kartlarının kodu, ünvanı veya tabela adı -> tahsilat
      4. Vergi numarası yoksa bölgesel firma adı fallback'i
      5. Yalnız tek tutar mutabakatı varsa otomatik sonuç

    Aynı vergi numaralı zincir müşteri birden fazla bölgede bulunabilir. Bu
    durumda müşteri listesindeki ``Şube`` alanı işlem bölgesini seçer. Vergi
    numarası yalnız tek şube altında bulunuyorsa, MANİM bölgesi farklı olsa bile
    bu tek grup güvenle kullanılabilir. Tahsilat raporundaki müşteri kodu ana
    listedeki koddan farklıysa ``Ünvan``/``Tabela Adi`` köprüsü kullanılır ve
    Netsis'e tahsilat satırındaki gerçek müşteri kodu gönderilir.
    """

    COMPANY_STOP_WORDS = {
        "A", "AS", "AŞ", "ANONIM", "ANONIMI", "SIRKET", "SIRKETI", "LTD", "LIMITED",
        "STI", "ŞTI", "SAN", "SANAYI", "TIC", "TICARET", "TUR", "TURIZM", "TURZ", "INS",
        "INSAAT", "NAK", "NAKLIYAT", "PAZ", "PAZARLAMA", "ENERJI", "GIDA", "TEM",
        "TEMIZLIK", "MAD", "MADDELERI", "TEKS", "TEKSTIL", "VE", "ILE", "SUBE",
        "SUBESI", "SB", "MERKEZ", "MERKEZI", "MARKET", "BUFE", "TEKEL", "AVM",
        "OTEL", "OTELCILIK", "TARIM", "URUNLERI", "URUN", "HIZMET", "HIZMETLERI",
    }
    BANK_STOP_WORDS = {
        "FAST", "EFT", "HAVALE", "FATURA", "ODEME", "ODEMESI", "TAHSILAT", "ACIKLAMA",
        "BANKA", "TL", "GELEN", "GOND", "GONDEREN", "CEP", "HVL", "MOBIL", "ISLEMI",
        "CARI", "SIGARA", "BORC", "TRANSFERI", "HESAP", "TICARI",
    }
    # Bir kelime, zincir markası belirteci sayılmak için en fazla kaç FARKLI
    # şirkette (VKN/ünvan grubunda) geçebilir. Bunun üzerindeki kelimeler
    # (örn. onlarca alakasız şirkette geçen genel bir kelime) güvenilmez sayılır.
    MAX_CHAIN_TOKEN_GROUPS = 15

    def __init__(
        self,
        tahsilat_records: list[TahsilatRecord],
        customers: list[CustomerRecord],
        store: MappingStore | None = None,
        region_branch_aliases: dict[str, tuple[str, ...]] | None = None,
    ):
        self.tahsilat_records = tahsilat_records
        self.customers = customers
        self.store = store or MappingStore()
        self.last_failure_reason = ""
        self.last_candidate_rows: list[TahsilatRecord] = []
        self.region_branch_aliases = {
            self._normalize(key): tuple(self._normalize(alias) for alias in aliases if str(alias).strip())
            for key, aliases in (region_branch_aliases or {}).items()
        }

        self._customers_by_code: dict[str, CustomerRecord] = {}
        self._tahsilat_by_code: dict[str, list[TahsilatRecord]] = defaultdict(list)
        for customer in customers:
            key = self._code_key(customer.cari_kodu)
            if key:
                self._customers_by_code[key] = customer
        for row in tahsilat_records:
            key = self._code_key(row.musteri_kodu)
            if key:
                self._tahsilat_by_code[key].append(row)

    def match(self, record: ManimRecord, region: str | None = None) -> list[TahsilatRecord] | None:
        self.last_failure_reason = ""
        self.last_candidate_rows = []
        mapped = self.store.get(record.aciklama)
        if mapped:
            rows = self._rows_from_mapping(mapped, record.tutar)
            if rows and self._reconciles(record.tutar, rows):
                return rows

        regional_customers = self._customers_for_region(region)

        # Vergi numarası önce müşteri listesinin TAMAMINDA aranır. Aynı VKN birden
        # fazla bölgede bulunuyorsa işlem bölgesi doğru şubeyi seçer. VKN yalnız
        # tek müşteri şubesinde bulunuyorsa, MANİM dosyasının bölgesi farklı olsa
        # bile bu tek ve kesin grup kullanılabilir. Gerçek raporlarda Muğla banka
        # hareketinin Bodrum müşteri kartlarına ait olabildiği görülmüştür.
        global_tax_groups = self._customer_groups_from_tax(record.aciklama, self.customers)
        if global_tax_groups:
            tax_groups = self._select_tax_groups_for_region(global_tax_groups, region)
            if tax_groups:
                match = self._match_customer_groups(record, tax_groups)
                if match:
                    return match
                # Bölgesel ilk deneme tutmazsa aynı VKN/TCKN'ye bağlı zincirin
                # tüm şubelerini de dene. Banka hareketi farklı bir bölge
                # hesabına yatmış olabilir; örneğin Denizli hareketinde Aydın
                # ve Nazilli şubelerinin tahsilatları birlikte yer alabilir.
                # Bu genişletme ancak tutar birebir ve tekil eşleşirse sonuç
                # döndürdüğünden yanlış şubeye otomatik aktarım yapmaz.
                chain_match = self._match_via_tabela_chain(record, global_tax_groups)
                if chain_match:
                    return chain_match
                self._set_amount_mismatch_reason(record, global_tax_groups)
                return None

            self.last_failure_reason = (
                "Vergi/T.C. numarası müşteri listesinde bulundu ancak aynı vergi numarası "
                "birden fazla bölgede bulunduğu için işlem bölgesine ait tek şube seçilemedi"
            )
            return None

        # VKN/TCKN bulunamadığında yalnız işlem bölgesindeki müşteri kartları
        # firma adı üzerinden denenir.
        name_groups = self._customer_groups_from_name(record.aciklama, regional_customers)
        match = self._match_customer_groups(record, name_groups)
        if match:
            return match

        # Müşteri ana listesi bulunmayan eski/test entegrasyonları için son
        # güvenli fallback. Ana liste varsa bölge filtresi korunur.
        direct_pool = self._direct_tahsilat_name_candidates(record.aciklama, region)
        return self._find_reconciling_subset(record.tutar, direct_pool)

    def _match_customer_groups(
        self,
        record: ManimRecord,
        groups: list[list[CustomerRecord]],
    ) -> list[TahsilatRecord] | None:
        successful: dict[tuple, list[TahsilatRecord]] = {}
        for group in groups:
            # Önemli: müşteri ana listesindeki kod ile tahsilat raporundaki kod
            # her zaman aynı değildir. Kodun yanında ünvan/tabela köprüsü de
            # kullanılır.
            rows = self._tahsilat_rows_for_customers(group)
            if not rows:
                continue

            dated_rows = self._same_date_rows(rows, record)
            for pool in (dated_rows, rows):
                if not pool:
                    continue
                subset = self._find_reconciling_subset(record.tutar, pool)
                if subset:
                    successful[self._rows_signature(subset)] = subset
                    break

        # Aynı tutarı sağlayan iki farklı cari dağılımı varsa tahmin yapılmaz.
        if len(successful) == 1:
            return next(iter(successful.values()))
        return None

    def _match_via_tabela_chain(
        self,
        record: ManimRecord,
        tax_groups: list[list[CustomerRecord]],
    ) -> list[TahsilatRecord] | None:
        """VKN eşleşen müşterinin kendi tahsilatı tutmuyorsa, aynı "zincir
        markasını" (Tabela Adı/Ünvan'daki ortak ayırt edici kelime, örn.
        büyük bir marketler zincirinde 'ZETA') paylaşan FARKLI vergi
        numaralı şube kartlarını da havuza katıp yeniden dener.

        Büyük zincir müşterilerde her şube ayrı vergi mükellefi olarak
        kayıtlı olabiliyor; personel birden fazla şubenin tahsilatını tek
        bir bankaya yatırdığında banka kaydı tek VKN'nin tahsilatıyla
        tutmaz ama zincirin TÜM şubelerinin toplamıyla tutabilir.

        Güvenlik: bir kelimenin kaç FARKLI şirkette (VKN/ünvan grubunda)
        geçtiği sayılır. 'TURZ' (Turizm kısaltması) gibi onlarca alakasız
        şirkette geçen genel kelimeler zincir belirteci sayılmaz; yalnızca
        az sayıda şirkette geçen (gerçek bir marka olma ihtimali yüksek)
        kelimeler kullanılır. Bulunan toplam tutar BİREBİR tutmuyorsa (ya da
        birden fazla olası kombinasyon varsa) hiçbir şey döndürülmez.
        """
        anchor_customers = [customer for group in tax_groups for customer in group]
        if not anchor_customers:
            return None

        # Aynı VKN/TCKN'li zincirin şubeleri farklı bölgelerde olsa bile önce
        # yalnız bu hukuki grubu dene. Nokta, kısaltma ya da şube adındaki
        # farklılıkları isimden çözmeye çalışmak yerine cari/VKN köprüsünü
        # kullanırız. Tutar tam ve tekil eşleşmedikçe sonuç dönmez.
        anchor_pool = self._tahsilat_rows_for_customers(anchor_customers)
        dated_anchor_rows = self._same_date_rows(anchor_pool, record)
        for candidate_pool in (dated_anchor_rows, anchor_pool):
            if not candidate_pool:
                continue
            subset = self._find_reconciling_subset(record.tutar, candidate_pool)
            if subset:
                return subset

        anchor_tokens: set[str] = set()
        for customer in anchor_customers:
            for alias in self._customer_aliases(customer):
                anchor_tokens.update(self._meaningful_company_tokens(alias, include_bank_words=True))
        anchor_tokens = {token for token in anchor_tokens if len(token) >= 4}
        if not anchor_tokens:
            return None

        anchor_codes = {self._code_key(customer.cari_kodu) for customer in anchor_customers}

        groups_by_key = self._group_customers(self.customers)
        group_tokens_cache: dict[str, set[str]] = {}
        token_group_counts: Counter[str] = Counter()
        for key, group in groups_by_key.items():
            tokens: set[str] = set()
            for customer in group:
                for alias in self._customer_aliases(customer):
                    tokens.update(self._meaningful_company_tokens(alias, include_bank_words=True))
            group_tokens_cache[key] = tokens
            token_group_counts.update(tokens)

        reliable_tokens = {
            token for token in anchor_tokens
            if 0 < token_group_counts.get(token, 0) <= self.MAX_CHAIN_TOKEN_GROUPS
        }
        if not reliable_tokens:
            return None

        chain_customers = list(anchor_customers)
        for key, group in groups_by_key.items():
            if any(self._code_key(customer.cari_kodu) in anchor_codes for customer in group):
                continue
            if group_tokens_cache[key] & reliable_tokens:
                chain_customers.extend(group)

        pool = self._tahsilat_rows_for_customers(chain_customers)
        dated_rows = self._same_date_rows(pool, record)
        for candidate_pool in (dated_rows, pool):
            if not candidate_pool:
                continue
            subset = self._find_reconciling_subset(record.tutar, candidate_pool)
            if subset:
                return subset
        return None

    def _customer_groups_from_name(
        self,
        description: str,
        customers: list[CustomerRecord],
    ) -> list[list[CustomerRecord]]:
        if not customers:
            return []

        description_tokens = set(self._meaningful_company_tokens(description, include_bank_words=False))
        if not description_tokens:
            return []

        groups = self._group_customers(customers)
        group_tokens: dict[str, set[str]] = {}
        token_frequency: Counter[str] = Counter()

        for key, group in groups.items():
            tokens: set[str] = set()
            for customer in group:
                for alias in self._customer_aliases(customer):
                    tokens.update(self._meaningful_company_tokens(alias, include_bank_words=True))
            group_tokens[key] = tokens
            token_frequency.update(tokens)

        scored: list[tuple[int, int, str, list[CustomerRecord]]] = []
        for key, group in groups.items():
            tokens = group_tokens[key]
            present = tokens & description_tokens
            if not present:
                continue

            unique_present = {token for token in present if len(token) >= 5 and token_frequency[token] == 1}
            if len(present) >= 2:
                score = 100 + len(present) * 10
            elif unique_present:
                score = 50 + max(len(token) for token in unique_present)
            else:
                continue

            longest = max((len(token) for token in present), default=0)
            scored.append((score, longest, key, group))

        if not scored:
            return []

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score = scored[0][0]
        return [group for score, _longest, _key, group in scored if score == best_score]

    def _customer_groups_from_tax(
        self,
        description: str,
        customers: list[CustomerRecord],
    ) -> list[list[CustomerRecord]]:
        by_variant: dict[str, dict[str, list[CustomerRecord]]] = defaultdict(lambda: defaultdict(list))
        for customer in customers:
            canonical = self._canonical_tax(customer.vergi_no)
            if not canonical:
                continue
            for variant in self._tax_variants(canonical):
                by_variant[variant][canonical].append(customer)

        matched_groups: dict[str, list[CustomerRecord]] = {}
        for digits in re.findall(r"(?<!\d)\d{9,11}(?!\d)", str(description)):
            for variant in self._tax_variants(digits):
                for canonical, group in by_variant.get(variant, {}).items():
                    matched_groups.setdefault(canonical, group)

        return list(matched_groups.values())


    def _select_tax_groups_for_region(
        self,
        groups: list[list[CustomerRecord]],
        region: str | None,
    ) -> list[list[CustomerRecord]]:
        """VKN gruplarında bölgesel şubeyi seçer.

        - Aynı VKN işlem bölgesinde bulunuyorsa yalnız o bölgenin kartları alınır.
        - VKN müşteri listesinde yalnız tek şube/bölge altında bulunuyorsa, MANİM
          dosyasının bölgesi farklı olsa bile tek ve kesin grup kullanılır.
        - VKN birden fazla bölgede olup işlem bölgesiyle eşleşmiyorsa otomatik
          karar verilmez.
        """
        selected: list[list[CustomerRecord]] = []
        for group in groups:
            if not group:
                continue
            if not region:
                selected.append(group)
                continue

            region_key = self._normalize(region)
            aliases = self.region_branch_aliases.get(region_key) or (region_key,)
            regional = [
                customer
                for customer in group
                if any(alias and alias in self._normalize(customer.sube) for alias in aliases)
            ]
            if regional:
                selected.append(regional)
                continue

            branch_keys = {
                self._normalize(customer.sube)
                for customer in group
                if str(customer.sube or "").strip()
            }
            if len(branch_keys) <= 1:
                selected.append(group)

        return selected

    def _set_amount_mismatch_reason(
        self,
        record: ManimRecord,
        groups: list[list[CustomerRecord]],
    ) -> None:
        candidate_rows: list[TahsilatRecord] = []
        seen: set[int] = set()
        for group in groups:
            for row in self._tahsilat_rows_for_customers(group):
                marker = id(row)
                if marker not in seen:
                    seen.add(marker)
                    candidate_rows.append(row)

        if not candidate_rows:
            self.last_failure_reason = (
                "Vergi/T.C. numarası ve müşteri kartı bulundu ancak tahsilat raporunda "
                "bu müşterilere ait satır bulunamadı"
            )
            return

        dated_rows = self._same_date_rows(candidate_rows, record)
        pool = dated_rows or candidate_rows
        self.last_candidate_rows = list(pool)
        candidate_total = sum(float(row.tutar) for row in pool)
        difference = round(float(record.tutar) - candidate_total, 2)
        self.last_failure_reason = (
            "Vergi/T.C. numarası ve müşteri şubeleri bulundu ancak tutarlar mutabık değil: "
            f"banka {record.tutar:,.2f} TL, tahsilat {candidate_total:,.2f} TL, "
            f"fark {difference:,.2f} TL"
        )

    def _customers_for_region(self, region: str | None) -> list[CustomerRecord]:
        if not region or not self.customers:
            return list(self.customers)

        # Ana listede hiç şube bilgisi yoksa eski veriyle uyumluluk için tüm
        # kartlar kullanılır. Şube bilgisi varsa eşleşmeyen bölge global havuza
        # düşürülmez; yanlış zincir şubesi seçmektense manuel inceleme güvenlidir.
        if not any(str(customer.sube or "").strip() for customer in self.customers):
            return list(self.customers)

        region_key = self._normalize(region)
        aliases = self.region_branch_aliases.get(region_key) or (region_key,)
        return [
            customer
            for customer in self.customers
            if any(alias and alias in self._normalize(customer.sube) for alias in aliases)
        ]

    def _tahsilat_rows_for_customers(self, customers: list[CustomerRecord]) -> list[TahsilatRecord]:
        rows: list[TahsilatRecord] = []
        seen_rows: set[int] = set()
        customer_codes = {self._code_key(customer.cari_kodu) for customer in customers}
        customer_codes.discard("")

        # 1) Kod birebir eşleşiyorsa en kesin köprü.
        for code in customer_codes:
            for row in self._tahsilat_by_code.get(code, []):
                marker = id(row)
                if marker not in seen_rows:
                    seen_rows.add(marker)
                    rows.append(row)

        # Kod birebir eşleşen tahsilat satırları bulunduysa isim köprüsünü
        # devreye sokma. Bu, aynı hukuki ünvanın başka bölgelerde de kullanıldığı
        # zincir müşterilerde çapraz bölge adayını engeller.
        if rows:
            return rows

        # 2) Kodlar farklıysa, bölgesel müşteri kartının gerçek Ünvan/Tabela
        # adını tahsilat raporundaki Müşteriİsmi ile karşılaştır.
        aliases = [
            alias
            for customer in customers
            for alias in self._customer_aliases(customer)
            if str(alias).strip()
        ]
        if aliases:
            for row in self.tahsilat_records:
                marker = id(row)
                if marker in seen_rows:
                    continue
                if any(self._business_names_match(row.musteri_ismi, alias) for alias in aliases):
                    seen_rows.add(marker)
                    rows.append(row)

        return rows

    def _direct_tahsilat_name_candidates(self, description: str, region: str | None) -> list[TahsilatRecord]:
        description_tokens = set(self._meaningful_company_tokens(description, include_bank_words=False))
        regional_customers = self._customers_for_region(region)
        if self.customers and region and not regional_customers:
            return []

        regional_codes = {self._code_key(customer.cari_kodu) for customer in regional_customers}
        candidates: list[TahsilatRecord] = []
        for row in self.tahsilat_records:
            # Kodlar farklı olabildiği için müşteri ana listesi mevcutken salt kod
            # filtresi uygulanmaz; ad köprüsü aşağıda güvenli biçimde çalışır.
            if not self.customers and regional_codes and self._code_key(row.musteri_kodu) not in regional_codes:
                continue
            tokens = set(self._meaningful_company_tokens(row.musteri_ismi, include_bank_words=True))
            present = tokens & description_tokens
            if not self.customers and present:
                candidates.append(row)
            elif len(present) >= 2 or any(len(token) >= 6 for token in present):
                candidates.append(row)
        return candidates

    @classmethod
    def _customer_aliases(cls, customer: CustomerRecord) -> list[str]:
        values = [customer.unvan, getattr(customer, "tabela_adi", "")]
        unique: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = cls._normalize(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(str(value))
        return unique

    @classmethod
    def _business_names_match(cls, tahsilat_name: str, customer_name: str) -> bool:
        left = cls._normalize(tahsilat_name)
        right = cls._normalize(customer_name)
        if not left or not right:
            return False
        if left == right:
            return True

        # Raporlardan biri şube/kişi ekini sonuna ekleyebilir.
        if min(len(left), len(right)) >= 12 and (left in right or right in left):
            return True

        left_tokens = set(cls._meaningful_company_tokens(left, include_bank_words=True))
        right_tokens = set(cls._meaningful_company_tokens(right, include_bank_words=True))
        if not left_tokens or not right_tokens:
            return False

        overlap = left_tokens & right_tokens
        smaller = min(len(left_tokens), len(right_tokens))
        # Hukuki ekler temizlendikten sonra iki güçlü kelime ve küçük adın en az
        # %75'i örtüşüyorsa aynı müşteri adı kabul edilir.
        return len(overlap) >= 2 and len(overlap) / smaller >= 0.75

    @staticmethod
    def _same_date_rows(rows: list[TahsilatRecord], record: ManimRecord) -> list[TahsilatRecord]:
        if record.islem_tarihi is None:
            return []
        target_date = record.islem_tarihi.date()
        return [row for row in rows if row.belge_tarihi and row.belge_tarihi.date() == target_date]

    @staticmethod
    def _rows_from_mapping(mapped: str | list[dict], amount: float) -> list[TahsilatRecord] | None:
        if isinstance(mapped, str):
            code = mapped.strip()
            if not code:
                return None
            return [TahsilatRecord(musteri_kodu=code, musteri_ismi="(manuel eşleştirme)", belge_tarihi=None, tutar=amount)]
        if isinstance(mapped, list):
            rows = []
            for item in mapped:
                try:
                    rows.append(TahsilatRecord(
                        musteri_kodu=str(item["musteri_kodu"]).strip(),
                        musteri_ismi="(manuel eşleştirme)",
                        belge_tarihi=None,
                        tutar=float(item["tutar"]),
                    ))
                except (KeyError, TypeError, ValueError):
                    return None
            return rows or None
        return None

    @classmethod
    def _find_reconciling_subset(cls, amount: float, rows: list[TahsilatRecord]) -> list[TahsilatRecord] | None:
        if not rows:
            return None
        if cls._reconciles(amount, rows):
            return rows
        if len(rows) > MAX_SUBSET_SEARCH_CANDIDATES:
            return None

        unique_matches: dict[tuple, list[TahsilatRecord]] = {}
        for size in range(1, len(rows)):
            for combo in combinations(rows, size):
                selected = list(combo)
                if cls._reconciles(amount, selected):
                    unique_matches[cls._rows_signature(selected)] = selected
                    if len(unique_matches) > 1:
                        return None
            if unique_matches:
                return next(iter(unique_matches.values())) if len(unique_matches) == 1 else None
        return None

    @classmethod
    def _group_customers(cls, customers: list[CustomerRecord]) -> dict[str, list[CustomerRecord]]:
        groups: dict[str, list[CustomerRecord]] = defaultdict(list)
        for customer in customers:
            tax = cls._canonical_tax(customer.vergi_no)
            key = f"TAX:{tax}" if tax else f"NAME:{cls._normalize(customer.unvan)}"
            groups[key].append(customer)
        return groups

    @classmethod
    def _meaningful_company_tokens(cls, value: str, include_bank_words: bool) -> list[str]:
        stop_words = set(cls.COMPANY_STOP_WORDS)
        if not include_bank_words:
            stop_words.update(cls.BANK_STOP_WORDS)
        return [
            token
            for token in cls._normalize(value).split()
            if len(token) >= 3 and token not in stop_words and not token.isdigit()
        ]

    @staticmethod
    def _canonical_tax(value: str) -> str:
        digits = re.sub(r"\D", "", str(value or ""))
        if len(digits) == 9:
            digits = digits.zfill(10)
        if len(digits) not in (10, 11):
            return ""
        if len(set(digits)) == 1:
            return ""
        return digits

    @classmethod
    def _tax_variants(cls, value: str) -> set[str]:
        digits = re.sub(r"\D", "", str(value or ""))
        variants = {digits} if digits else set()
        canonical = cls._canonical_tax(digits)
        if canonical:
            variants.add(canonical)
            if canonical.startswith("0"):
                variants.add(canonical[1:])
        return {variant for variant in variants if variant}

    @staticmethod
    def _code_key(value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())

    @staticmethod
    def _rows_signature(rows: list[TahsilatRecord]) -> tuple:
        return tuple(sorted(
            (
                SubeliMatcher._code_key(row.musteri_kodu),
                round(float(row.tutar), 2),
                row.belge_tarihi.isoformat() if row.belge_tarihi else "",
            )
            for row in rows
        ))

    @staticmethod
    def _normalize(value: str) -> str:
        value = unicodedata.normalize("NFKD", str(value).upper())
        value = "".join(char for char in value if not unicodedata.combining(char))
        return re.sub(r"[^A-Z0-9]+", " ", value).strip()

    @classmethod
    def _reconciles(cls, amount: float, rows: list[TahsilatRecord]) -> bool:
        if not rows:
            return False
        target_cents = cls._to_cents(amount)
        row_cents = sum(cls._to_cents(row.tutar) for row in rows)
        # Gerçek raporlarda toplam ile banka hareketi arasında 1 kuruşluk yuvarlama
        # farkı oluşabiliyor. Para hesabı float yerine kuruş cinsinden yapılır.
        return abs(row_cents - target_cents) <= 1

    @staticmethod
    def _to_cents(value: float) -> int:
        try:
            amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError):
            return 0
        return int(amount * 100)
