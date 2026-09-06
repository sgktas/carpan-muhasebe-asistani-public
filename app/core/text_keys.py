from __future__ import annotations

import re
import unicodedata


def decode_hash_unicode(value: object) -> str:
    """ZIP/aktarım sırasında ``#U00d6`` biçimine dönen harfleri çözer."""
    return re.sub(
        r"#U([0-9A-Fa-f]{4})",
        lambda match: chr(int(match.group(1), 16)),
        str(value),
    )


def normalized_words(value: object) -> str:
    text = unicodedata.normalize("NFKD", decode_hash_unicode(value).upper())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("İ", "I").replace("ı", "I")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


def compact_key(value: object) -> str:
    return normalized_words(value).replace(" ", "")


def customer_code_key(value: object) -> str:
    return "".join(str(value).strip().upper().split())


def bank_key(value: object) -> str:
    normalized = normalized_words(value)
    if "GARANTI" in normalized:
        return "GARANTI"
    if "ZIRAAT" in normalized:
        return "ZIRAAT"
    if "YAPI" in normalized or "YKB" in normalized:
        return "YKB"
    return re.sub(r"[^A-Z0-9]+", "_", normalized).strip("_") or "BILINMEYEN_BANKA"
