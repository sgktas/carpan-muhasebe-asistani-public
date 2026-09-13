"""P1 için Excel binary yerine muhasebe anlamını donduran test yardımcıları."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path

import xlrd


GOLDEN_ROOT = Path(__file__).with_name("golden")


def canonical_decimal(value: object) -> str:
    """Para değerini platform ve float gösteriminden bağımsız iki haneye indirger."""
    return format(
        Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        ".2f",
    )


def canonical_netsis_records(records) -> dict:
    rows = [
        {
            "date": record.islem_tarihi.date().isoformat() if record.islem_tarihi else None,
            "customer_code": record.cari_kodu,
            "amount": canonical_decimal(record.tutar),
            "bank": record.banka,
            "region": record.bolge,
            "source_type": record.kaynak,
        }
        for record in records
    ]
    return {
        "rows": sorted(rows, key=lambda row: (row["customer_code"], row["amount"])),
        "total": canonical_decimal(sum(Decimal(row["amount"]) for row in rows)),
    }


def canonical_netsis_xls(path: Path) -> dict:
    """Üretilmiş BIFF8 Netsis dosyasından muhasebe satırlarını yeniden okur."""
    workbook = xlrd.open_workbook(str(path))
    sheet = workbook.sheet_by_index(0)
    headers = {str(value): index for index, value in enumerate(sheet.row_values(0))}
    required = ("İşlem Tarihi(*)", "Cari Kodu(*)", "Tutar", "Açıklama", "Proje Kodu(*)")
    assert all(header in headers for header in required), "Netsis semantic columns are missing"
    rows = []
    for row_index in range(1, sheet.nrows):
        amount = sheet.cell_value(row_index, headers["Tutar"])
        if amount in (None, ""):
            continue
        date_value = xlrd.xldate_as_datetime(
            sheet.cell_value(row_index, headers["İşlem Tarihi(*)"]), workbook.datemode
        ).date().isoformat()
        rows.append({
            "date": date_value,
            "customer_code": str(sheet.cell_value(row_index, headers["Cari Kodu(*)"])),
            "amount": canonical_decimal(amount),
            "description": str(sheet.cell_value(row_index, headers["Açıklama"])),
            "project_code": str(int(sheet.cell_value(row_index, headers["Proje Kodu(*)"]))),
        })
    return {
        "rows": sorted(rows, key=lambda row: (row["date"], row["customer_code"])),
        "row_count": len(rows),
        "total": canonical_decimal(sum(Decimal(row["amount"]) for row in rows)),
    }


def canonical_processing_result(result) -> dict:
    """Yol, zaman, dosya adı ve log metni olmadan karar sonucunu özetler."""
    decisions = [
        {
            "region": item["region"],
            "bank": item["bank"],
            "amount": canonical_decimal(item["amount"]),
            "outcome": item["outcome"],
            "rule_code": item["rule_code"],
        }
        for item in result.decision_audits
    ]
    return {
        "summary": {
            "source_records": result.total_manim_records,
            "resolved": result.produced_netsis_records,
            "unresolved": result.unresolved,
            "payment_approved": result.skipped_payment,
            "referenced": result.skipped_reference,
            "virman": result.virman_records,
            "consumed_collection_rows": result.consumed_tahsilat_rows,
        },
        "decisions": sorted(
            decisions,
            key=lambda item: (Decimal(item["amount"]), item["outcome"]),
        ),
    }


def canonical_reconciliation_result(result) -> dict:
    return {
        "matched": result.eslesen_sayisi,
        "grouped_matches": result.bolunmus_grup_sayisi,
        "balanced": result.mutabik,
        "difference": canonical_decimal(result.fark) if result.fark is not None else None,
        "bank_unmatched": [canonical_decimal(item.tutar) for item in result.sadece_bankada],
        "netsis_unmatched": [canonical_decimal(item.tutar) for item in result.sadece_netposte],
    }


def canonical_report_result(result) -> dict:
    return result.summary()


def load_golden(name: str) -> dict:
    return json.loads((GOLDEN_ROOT / f"{name}.json").read_text(encoding="utf-8"))


def assert_matches_golden(name: str, actual: dict) -> None:
    expected = load_golden(name)
    assert actual == expected, (
        f"Golden regression mismatch: {name}\n"
        f"Expected:\n{json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True)}\n"
        f"Actual:\n{json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True)}"
    )
