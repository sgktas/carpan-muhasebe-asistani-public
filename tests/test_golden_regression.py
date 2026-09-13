"""P1: P2 refactor öncesi sentetik muhasebe davranışı golden sözleşmeleri."""
from dataclasses import replace
from datetime import datetime

from openpyxl import Workbook
import pytest

from app.core.reconciliation_engine import ReconciliationEngine
from app.core.tahsilat_consumption_ledger import TahsilatConsumptionError, TahsilatConsumptionLedger
from app.modules.report_editing.engine import ReportEditingEngine
from app.models.records import (
    BankStatementRecord,
    CustomerRecord,
    ManimRecord,
    NetsisReportRecord,
    TahsilatRecord,
)
from app.processors.havale_processor import HavaleProcessor
from app.core.processing_engine import ProcessingEngine
from tests.golden_helpers import (
    assert_matches_golden,
    canonical_netsis_xls,
    canonical_netsis_records,
    canonical_processing_result,
    canonical_reconciliation_result,
    canonical_report_result,
)


TEST_TAX_ID = "1" * 9 + "2"


def _movement(description: str, amount: float, *, bank="TestBankA") -> ManimRecord:
    return ManimRecord(
        banka=bank, sube="TestBranch", islem_tarihi=datetime(2026, 1, 15),
        aciklama=description, tutar=amount, dekont_durumu="Aktarıldı",
        karsi_hesap_adi="", karsi_hesap_kodu="", kaynak_dosya="synthetic.xlsx", kaynak_satir=2,
    )


def _bank(amount: float, row: int = 1) -> BankStatementRecord:
    return BankStatementRecord(datetime(2026, 1, 15), "SYNTHETIC GROUP", amount, amount, "bank.xlsx", row)


def _netsis(amount: float, row: int = 1) -> NetsisReportRecord:
    return NetsisReportRecord(datetime(2026, 1, 15), "SYNTHETIC GROUP", amount, amount, "netsis.xlsx", row)


def test_golden_manim_normal_end_to_end(synthetic_project):
    result = ProcessingEngine(list(synthetic_project[:3]), synthetic_project[3]).run()
    actual = canonical_processing_result(result)
    assert_matches_golden("manim_normal", actual)
    assert result.total_manim_records == result.produced_netsis_records + result.skipped_payment + result.skipped_reference + result.unresolved
    netsis_outputs = [
        path for path in result.created_files
        if path.suffix == ".xls" and "BODRUM_GARANTI" in path.name
    ]
    assert len(netsis_outputs) == 1
    output_semantics = canonical_netsis_xls(netsis_outputs[0])
    assert_matches_golden("netsis_output_normal", output_semantics)
    assert output_semantics["row_count"] == result.produced_netsis_records
    assert output_semantics["total"] == "1000.00"


def test_golden_btd_masked_customer_code_routing():
    processor = HavaleProcessor([], [CustomerRecord("BTDTESTB100", "SYNTHETIC", TEST_TAX_ID, "TEST_REGION_A")])
    rows, reason = processor.process(_movement("BTD**TESTB100", 120), "TEST_REGION_A")
    assert reason is None
    canonical_rows = [replace(row, bolge="TEST_REGION_A") for row in rows]
    assert_matches_golden("manim_btd", canonical_netsis_records(canonical_rows))


def test_golden_tax_and_branch_collection_conservation():
    customer = CustomerRecord("TESTT200", "SYNTHETIC CHAIN", TEST_TAX_ID, "TEST_REGION_B")
    collection = TahsilatRecord("TESTT200", "SYNTHETIC CHAIN", datetime(2026, 1, 16), 250)
    processor = HavaleProcessor([collection], [customer])
    movement = _movement(f"SYNTHETIC CHAIN {TEST_TAX_ID}", 250, bank="TestBankB")
    rows, reason = processor.process(movement, "TEST_REGION_B")
    assert reason is None
    assert sum(row.tutar for row in rows) == movement.tutar
    canonical_rows = [replace(row, bolge="TEST_REGION_B") for row in rows]
    assert_matches_golden("manim_tax_and_branch", canonical_netsis_records(canonical_rows))


def test_golden_unresolved_movement_produces_no_netsis_row():
    processor = HavaleProcessor([], [])
    rows, reason = processor.process(_movement("UNKNOWN SYNTHETIC PARTY", 80), "TEST_REGION_A")
    assert rows == []
    assert reason
    assert_matches_golden("manim_unresolved", canonical_netsis_records(rows))


def test_golden_duplicate_source_contract(synthetic_project):
    files = list(synthetic_project[:3])
    first = ProcessingEngine(files, synthetic_project[3]).run()
    second = ProcessingEngine(files, synthetic_project[3]).run()
    assert first.produced_netsis_records == 1
    assert second.produced_netsis_records == 0
    assert second.duplicate_files == [synthetic_project[0].name]


def test_golden_collection_consumption_is_idempotent(tmp_path):
    ledger = TahsilatConsumptionLedger(tmp_path / "ledger.sqlite3", company_id=1)
    source = TahsilatRecord(
        "TESTT200", "SYNTHETIC", None, 250,
        source_hash="synthetic-source", source_sheet="Sheet1", source_row=2, source_amount=250,
    )
    assert ledger.consume([source], operation_id=101) == 1
    assert ledger.available_rows([source]) == []
    with pytest.raises(TahsilatConsumptionError, match="kullanılabilir bakiyesi"):
        ledger.consume([source], operation_id=102)


def test_golden_reconciliation_exact_and_grouped():
    exact = ReconciliationEngine().reconcile([_bank(100)], [_netsis(100)])
    assert_matches_golden("reconciliation_exact", canonical_reconciliation_result(exact))
    grouped_rows = [replace(_netsis(100), bakiye=250), replace(_netsis(150, 2), bakiye=250)]
    grouped = ReconciliationEngine().reconcile([_bank(250)], grouped_rows)
    assert_matches_golden("reconciliation_grouped", canonical_reconciliation_result(grouped))
    assert sum(item.tutar for item in grouped_rows) == 250


def test_golden_report_editing_basic(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
        "MusteriKodu", "Musteriİsmi", "BelgeNo", "BelgeTarihi", "TahsilatTipi",
        "TahsilatTuru", "SatisElemani", "Pesin/Diger", "Personel", "Rota",
        "MusteriKayitTipi", "MusteriTipi", "SahiplikTipi", "AltTip", "FiyatListesi", "BANKA", "Tutar",
    ])
    sheet.append(["TEST-R1", "SYNTHETIC", "DOC-1", "15.01.2026", "N", "1", "P1", 0, "P", "TEST-DD-01", "Müşteri", "Müşteri", "Bağımsız", "Market", "Liste", "TestBankA", 80])
    source = tmp_path / "collections.xlsx"
    workbook.save(source)
    result = ReportEditingEngine([source], resource_root=tmp_path, output_root=tmp_path / "out", create_template_outputs=False).run()
    assert_matches_golden("report_editing_basic", canonical_report_result(result))
