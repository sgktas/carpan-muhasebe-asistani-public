import json
import os
from pathlib import Path
import re
import shutil
from tempfile import NamedTemporaryFile


class RegionConfig:
    """config/bolge_kodlari.json dosyasını okur.

    Yeni bir bölge (ya da bir bölgeye yeni bir banka) eklemek için bu JSON
    dosyasına bir satır eklemek yeterlidir; Python kodunda değişiklik
    gerekmez. Alanlar tanınmayan bir bölge için None döner; çağıran taraf bu
    durumda o kaydı "İnceleme Gerekenler"e düşürmelidir (sessizce varsayılan
    bir kod uydurmak yerine).
    """

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self._raw = self._load_raw()
        self._data = {key: value for key, value in self._raw.items() if not key.startswith("_")}

    def _load_raw(self) -> dict:
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def plasiyer_kodu(self) -> str:
        return self._raw.get("_plasiyer_kodu", "00")

    def genel_ref_kodu(self) -> str:
        return self._raw.get("_genel_ref_kodu", "G01")

    def regions(self, include_inactive: bool = False) -> tuple[str, ...]:
        """Bölgeleri kullanıcı tarafından belirlenen işlem sırasıyla döndürür."""
        indexed = list(enumerate(self._data.items()))
        if not include_inactive:
            indexed = [item for item in indexed if item[1][1].get("aktif", True)]
        indexed.sort(
            key=lambda item: (
                int(item[1][1].get("sira", item[0] + 1)),
                item[0],
            )
        )
        return tuple(item[1][0] for item in indexed)

    def entry(self, region: str) -> dict:
        return dict(self._data.get(str(region).strip().upper(), {}))

    def kasa_kodu(self, region: str) -> int | None:
        return self._data.get(region, {}).get("kasa_kodu")

    def proje_kodu(self, region: str) -> int | None:
        return self._data.get(region, {}).get("proje_kodu")

    def ref_kodu(self, region: str) -> str | None:
        return self._data.get(region, {}).get("ref_kodu")

    def banka_kodu(self, region: str, bank: str) -> str | None:
        return self._data.get(region, {}).get("banka_kodlari", {}).get(bank)

    def manim_hesap_kodu(self, region: str, bank: str) -> str | None:
        return self._data.get(region, {}).get("manim_hesap_kodlari", {}).get(bank)

    def find_region_by_manim_account(self, bank: str, account_code: str) -> str | None:
        """Banka ve MANİM hesap/IBAN değerinin son hanelerinden bölgeyi bulur."""
        bank_key = str(bank or "").strip().upper()
        account_candidates = self._account_candidate_keys(account_code)
        if not bank_key or not account_candidates:
            return None

        matches: list[tuple[str, str]] = []
        for region in self.regions():
            suffix = self._account_key(self.manim_hesap_kodu(region, bank_key))
            if suffix and any(candidate.endswith(suffix) for candidate in account_candidates):
                matches.append((region, suffix))
        if not matches:
            return None

        # Bir gün kısa ve uzun iki son-hane kuralı çakışırsa daha ayrıntılı olan
        # uzun değer kazanır. Aynı uzunlukta birden fazla sonuç varsa otomatik
        # karar verilmez.
        longest = max(len(suffix) for _region, suffix in matches)
        most_specific = [region for region, suffix in matches if len(suffix) == longest]
        return most_specific[0] if len(most_specific) == 1 else None

    def customer_branch_aliases(self, region: str) -> tuple[str, ...]:
        aliases = self._data.get(region, {}).get("musteri_sube_etiketleri", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        cleaned = tuple(str(alias).strip() for alias in aliases if str(alias).strip())
        return cleaned or (region,)

    def is_complete(self, region: str) -> bool:
        entry = self._data.get(region)
        if not entry:
            return False
        return entry.get("kasa_kodu") is not None and entry.get("proje_kodu") is not None

    def find_region_in_text(self, text: str) -> str | None:
        """Verilen metinde (örn. banka ekstresi/Netsis raporu antet bloğu)
        bilinen bir bölge geçip geçmediğini arar.

        Önce ``banka_kodlari`` altındaki kodlar (örn. 'BANK-G-01') aranır —
        bunlar en kesin işaretçidir, çünkü her bölge+banka kombinasyonuna
        özeldir. Bulunamazsa ``musteri_sube_etiketleri`` (örn. 'BODRUM')
        adı metinde geçip geçmediğine bakılır.
        """
        if not text:
            return None
        upper_text = text.upper()

        for region in self.regions():
            entry = self._data[region]
            for code in entry.get("banka_kodlari", {}).values():
                if code and str(code).upper() in upper_text:
                    return region

        for region in self.regions():
            for alias in self.customer_branch_aliases(region):
                if alias and alias.upper() in upper_text:
                    return region

        return None

    @staticmethod
    def _account_key(value: object) -> str:
        text = str(value or "").strip().upper()
        if re.fullmatch(r"\d+\.0+", text):
            text = text.split(".", 1)[0]
        return re.sub(r"[^A-Z0-9]+", "", text)

    @classmethod
    def _account_candidate_keys(cls, value: object) -> tuple[str, ...]:
        """Hesabın tamamını ve ayrılmış parçalarını eşleşme adayı yapar.

        MANİM alanı yalnız bir hesap/IBAN içerebildiği gibi
        ``Garanti-Antalya Ticari-0509-Vadesiz TRY`` biçiminde açıklamalı da
        gelebilir. Bu ikinci biçimde hesap kodu metnin sonunda olmadığı için
        yalnız tüm alan üzerinde ``endswith`` kullanmak kodu kaçırır.
        """
        text = str(value or "").strip().upper()
        if not text:
            return ()

        candidates = [cls._account_key(text)]
        candidates.extend(
            cls._account_key(part)
            for part in re.findall(r"[A-Z0-9]+", text)
        )
        return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))


def active_region_config_path(resource_config_dir: str | Path, data_root: str | Path) -> Path:
    """Paket içindeki varsayılanı ilk kullanımda yazılabilir kullanıcı alanına kopyalar."""
    resource_config_dir = Path(resource_config_dir)
    local_source = resource_config_dir / "local" / "bolge_kodlari.json"
    if os.environ.get("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG") == "1":
        local_source = resource_config_dir / "__local_config_disabled__"
    source = local_source if local_source.exists() else resource_config_dir / "bolge_kodlari.json"
    target = Path(data_root) / "config" / "bolge_kodlari.json"
    if source.resolve() == target.resolve():
        return source
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() and source.exists():
        shutil.copy2(source, target)
    elif target.exists() and source.exists():
        _merge_missing_region_defaults(source, target)
    return target


def _merge_missing_region_defaults(source: Path, target: Path) -> None:
    """Yeni sürüm alanlarını kullanıcı düzenlemelerini bozmadan hedefe ekler."""
    try:
        defaults = json.loads(source.read_text(encoding="utf-8"))
        current = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    current_version = int(current.get("_config_surumu", 0) or 0)
    default_version = int(defaults.get("_config_surumu", 0) or 0)
    changed = False
    for key, default_value in defaults.items():
        if key not in current:
            current[key] = default_value
            changed = True
            continue
        if key.startswith("_") or not isinstance(default_value, dict):
            continue
        existing = current.get(key)
        if not isinstance(existing, dict):
            continue
        for field, value in default_value.items():
            if field not in existing:
                existing[field] = value
                changed = True
                continue
            # Banka listeleri zamanla genişleyebilir. Eski kullanıcı
            # ayarlarında yeni bir banka (örn. ANTALYA / AKBANK) yoksa,
            # bölgenin mevcut kodlarını değiştirmeden yalnız eksik anahtarı ekle.
            if field in {"banka_kodlari", "manim_hesap_kodlari"}:
                current_codes = existing.get(field)
                default_codes = value
                if not isinstance(current_codes, dict) or not isinstance(default_codes, dict):
                    continue
                for bank, code in default_codes.items():
                    if bank not in current_codes:
                        current_codes[bank] = code
                        changed = True

    # Revize 20: Nazilli artık Aydın operasyonunun zorunlu ikinci aktif bölgesi.
    # Eski kullanıcı kopyalarında `aktif:false` bulunduğundan yalnız bu sürüm
    # geçişinde varsayılan karar bilinçli olarak uygulanır. Sonraki kullanıcı
    # değişiklikleri config sürümü güncel olduğu için korunur.
    if current_version < 2 <= default_version and isinstance(current.get("NAZILLI"), dict):
        if not current["NAZILLI"].get("aktif", True):
            current["NAZILLI"]["aktif"] = True
            changed = True

    if current.get("_config_surumu") != default_version:
        current["_config_surumu"] = default_version
        changed = True

    if changed:
        target.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


class RegionConfigStore:
    """Ayarlar ekranının bölge yapılandırmasını güvenli biçimde yönetir."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def config(self) -> RegionConfig:
        return RegionConfig(self.file_path)

    @staticmethod
    def normalize_name(value: str) -> str:
        replacements = str.maketrans("ÇĞİÖŞÜçğıöşü", "CGIOSUCGIOSU")
        normalized = str(value or "").strip().upper().translate(replacements)
        return "_".join(normalized.split())

    def save_region(self, name: str, values: dict, original_name: str | None = None) -> str:
        region = self.normalize_name(name)
        if not region:
            raise ValueError("Bölge adı boş bırakılamaz.")

        raw = self._load_raw()
        original = self.normalize_name(original_name or "")
        if original and original != region:
            raw.pop(original, None)

        current = raw.get(region, {}) if isinstance(raw.get(region), dict) else {}
        current.update(values)
        current["aktif"] = bool(current.get("aktif", True))
        current["sira"] = max(1, int(current.get("sira", 1)))
        current["musteri_sube_etiketleri"] = [
            str(item).strip().upper()
            for item in current.get("musteri_sube_etiketleri", [])
            if str(item).strip()
        ] or [region]
        current["banka_kodlari"] = {
            str(bank).strip().upper(): str(code).strip().upper()
            for bank, code in current.get("banka_kodlari", {}).items()
            if str(bank).strip() and str(code).strip()
        }
        current["manim_hesap_kodlari"] = {
            str(bank).strip().upper(): str(code).strip().upper()
            for bank, code in current.get("manim_hesap_kodlari", {}).items()
            if str(bank).strip() and str(code).strip()
        }
        raw[region] = current
        self._write_raw(raw)
        return region

    def next_order(self) -> int:
        orders = [
            int(entry.get("sira", index + 1))
            for index, (key, entry) in enumerate(self._load_raw().items())
            if not key.startswith("_") and isinstance(entry, dict)
        ]
        return max(orders, default=0) + 1

    def _load_raw(self) -> dict:
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(f"Bölge ayar dosyası okunamıyor: {error}") from error

    def _write_raw(self, raw: dict) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.file_path.parent,
            prefix="bolge_kodlari-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(raw, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            temporary_path = Path(handle.name)
        temporary_path.replace(self.file_path)
