from __future__ import annotations

from app.core.operation_history import OperationHistory
from app.modules.bank_reconciliation.page import BankReconciliationPage
from app.modules.base import ModuleManifest
from app.modules.cari_reconciliation.page import CariReconciliationPage
from app.modules.customer_list.page import CustomerListPage
from app.modules.manim.page import ManimModulePage
from app.modules.report_editing.page import ReportEditingPage


def build_module_registry(history: OperationHistory) -> list[ModuleManifest]:
    return [
        ModuleManifest(
            module_id="manim_transfer",
            name="MANİM Aktarma",
            nav_label="MANİM Aktarma",
            version="1.3.0",
            icon_name="transfer",
            badge="MODÜL 01",
            description="MANİM ve tahsilat verilerini Netsis aktarımına hazırlar.",
            page_factory=lambda: ManimModulePage(history),
        ),
        ModuleManifest(
            module_id="report_editing",
            name="FOM Rapor Düzenleme",
            nav_label="FOM Rapor Düzenleme",
            version="1.2.0",
            icon_name="report",
            badge="MODÜL 02",
            description="Müşteri, satış ve tahsilat raporlarını standartlaştırır.",
            page_factory=lambda: ReportEditingPage(history),
        ),
        ModuleManifest(
            module_id="bank_reconciliation",
            name="Banka Mutabakatı",
            nav_label="Banka Mutabakatı",
            version="0.1.0",
            icon_name="folder",
            badge="MODÜL 03",
            description="Banka ekstresi ile Netsis kayıtlarını karşılaştırıp farkları raporlar.",
            page_factory=lambda: BankReconciliationPage(history),
        ),
        ModuleManifest(
            module_id="cari_reconciliation",
            name="Cari Mutabakat",
            nav_label="Cari Mutabakat",
            version="0.1.0",
            icon_name="upload",
            badge="MODÜL 04",
            description="Müşteri bazında Netsis bakiyesi ile kayıtları karşılaştırıp mutabakat raporu hazırlar.",
            page_factory=lambda: CariReconciliationPage(history),
        ),
        ModuleManifest(
            module_id="customer_list_import",
            name="Müşteri Listesi",
            nav_label="Müşteri Listesi",
            version="1.0.0",
            icon_name="upload",
            badge="MODÜL 05",
            description="Ham FOM müşteri listesini düzenler ve MANİM için hafızaya alır.",
            page_factory=lambda: CustomerListPage(history),
        ),
    ]
