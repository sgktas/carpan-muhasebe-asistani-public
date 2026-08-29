from __future__ import annotations

import argparse
import io
from pathlib import Path
import re
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_SPREADSHEETS: set[str] = set()
FORBIDDEN_PATH_PARTS = {
    "revize_notlari.md",
    "ak-personel listesi.xlsx",
}
TEXT_SUFFIXES = {
    ".bat", ".cfg", ".ini", ".json", ".md", ".ps1", ".py", ".sh",
    ".toml", ".txt", ".xml", ".yaml", ".yml",
}
SECRET_PATTERNS = {
    "GitHub erişim anahtarı": re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}"),
    "AWS erişim anahtarı": re.compile(r"AKIA[0-9A-Z]{16}"),
    "özel anahtar": re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY"),
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IBAN_RE = re.compile(r"\bTR[0-9]{24}\b", re.IGNORECASE)
LONG_ID_RE = re.compile(r"(?<!\d)(\d{10,11})(?!\d)")
PHONE_RE = re.compile(r"(?<!\d)(0?5\d{9})(?!\d)")
INTERNAL_CODE_RE = re.compile(r"\bBM21\d{3}\b", re.IGNORECASE)


def git_files(staged: bool) -> list[str]:
    command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged else ["git", "ls-files"]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode == 0:
        return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]
    excluded = (".git", "config/local", "inputs", "local_data", "outputs", "templates/local")
    return [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(
            path.relative_to(ROOT).as_posix() == prefix
            or path.relative_to(ROOT).as_posix().startswith(f"{prefix}/")
            for prefix in excluded
        )
    ]


def file_bytes(relative_path: str, staged: bool) -> bytes:
    if staged:
        completed = subprocess.run(
            ["git", "show", f":{relative_path}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if completed.returncode == 0:
            return completed.stdout
    return (ROOT / relative_path).read_bytes()


def synthetic_long_id(value: str) -> bool:
    return (
        len(set(value)) == 1
        or value == "0111111111"
        or value == "05000000000"
        or value == "1000000000"
        or re.fullmatch(r"100000000[1-9]", value) is not None
        or re.fullmatch(r"1000000000[1-9]", value) is not None
    )


def scan_text(relative_path: str, payload: bytes) -> list[str]:
    text = payload.decode("utf-8", errors="replace")
    errors: list[str] = []
    for label, pattern in SECRET_PATTERNS.items():
        if pattern.search(text):
            errors.append(f"{relative_path}: {label} olabilecek değer bulundu")
    for email in EMAIL_RE.findall(text):
        if not email.lower().endswith("@example.com"):
            errors.append(f"{relative_path}: gerçek olabilecek e-posta adresi bulundu")
            break
    for iban in IBAN_RE.findall(text):
        if iban.upper() != "TR000000000000000000000000":
            errors.append(f"{relative_path}: gerçek olabilecek IBAN bulundu")
            break
    for phone in PHONE_RE.findall(text):
        if phone != "05000000000":
            errors.append(f"{relative_path}: gerçek olabilecek telefon numarası bulundu")
            break
    for identifier in LONG_ID_RE.findall(text):
        if not synthetic_long_id(identifier):
            errors.append(f"{relative_path}: gerçek olabilecek 10/11 haneli kimlik/vergi değeri bulundu")
            break
    if INTERNAL_CODE_RE.search(text):
        errors.append(f"{relative_path}: gerçek şirket içi banka kodu biçimi bulundu")
    return errors


def workbook_row_count(relative_path: str, payload: bytes) -> int:
    suffix = Path(relative_path).suffix.lower()
    if suffix == ".xlsx":
        try:
            import openpyxl
        except ModuleNotFoundError as error:
            raise RuntimeError("Excel güvenlik taraması için openpyxl kurulmalıdır") from error
        workbook = openpyxl.load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
        return max(
            sum(1 for row in sheet.iter_rows(values_only=True) if any(value not in (None, "") for value in row))
            for sheet in workbook.worksheets
        )
    try:
        import xlrd
    except ModuleNotFoundError as error:
        raise RuntimeError("Excel güvenlik taraması için xlrd kurulmalıdır") from error
    with tempfile.NamedTemporaryFile(suffix=".xls") as handle:
        handle.write(payload)
        handle.flush()
        workbook = xlrd.open_workbook(handle.name, on_demand=True)
        return max(
            sum(1 for row_index in range(sheet.nrows) if any(value not in (None, "") for value in sheet.row_values(row_index)))
            for sheet in workbook.sheets()
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Public depoya hassas veri eklenmesini engeller.")
    parser.add_argument("--staged", action="store_true", help="Yalnız commit için hazırlanmış dosyaları tara")
    args = parser.parse_args()
    errors: list[str] = []

    for relative_path in git_files(args.staged):
        normalized = relative_path.replace("\\", "/")
        lowered = normalized.casefold()
        if any(part in lowered for part in FORBIDDEN_PATH_PARTS):
            errors.append(f"{normalized}: public depoda yasaklı hassas dosya adı")
            continue
        path = ROOT / normalized
        if not path.exists() and not args.staged:
            continue
        payload = file_bytes(normalized, args.staged)
        suffix = Path(normalized).suffix.lower()
        if suffix in {".xlsx", ".xls", ".csv", ".tsv"}:
            if normalized not in ALLOWED_SPREADSHEETS:
                errors.append(f"{normalized}: public depoda izin verilmeyen veri dosyası")
                continue
            rows = workbook_row_count(normalized, payload)
            if rows > 1:
                errors.append(f"{normalized}: şablonda başlık dışında {rows - 1} dolu satır bulundu")
        elif suffix in TEXT_SUFFIXES:
            errors.extend(scan_text(normalized, payload))

    if errors:
        print("PUBLIC VERİ GÜVENLİĞİ KONTROLÜ BAŞARISIZ:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public veri güvenliği kontrolü başarılı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
