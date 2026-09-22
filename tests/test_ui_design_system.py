from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QScrollArea
from PySide6.QtTest import QTest
from PySide6.QtCore import QPoint

from app.core import identity
from app.core.identity import IdentityStore
from app.ui import main_window
from app.ui.components import SidebarItem
from app.ui.components import ModuleStatusBadge, StatusBadge
from app.ui.product_registry import (
    ACTIVE,
    COMING_SOON,
    LOCKED,
    UNCONFIGURED,
    PRODUCT_MODULES,
    grouped_product_modules,
)


_APP = QApplication.instance() or QApplication([])


def test_accounting_parent_and_chevron_toggle_without_changing_workspace(tmp_path, monkeypatch):
    window = _window(tmp_path, monkeypatch)
    window.resize(1600, 900)
    window.show()
    window._open_accounting_mode('new')
    _APP.processEvents()
    item = next(item for (key, _), item in zip(window.nav_items, window.nav_item_widgets) if key == 'accounting_automation')
    page = window.pages.currentWidget()
    assert not window.accounting_subnav.isHidden()
    item.button.click()
    assert window.accounting_subnav.isHidden()
    assert item.chevron.text() == '⌄'
    item.chevron.click()
    assert not window.accounting_subnav.isHidden()
    assert item.chevron.text() == '⌃'
    assert window.pages.currentWidget() is page
    assert not item.button.geometry().intersects(item.chevron.geometry())
    item.button.click()
    window._toggle_sidebar()
    window._toggle_sidebar()
    assert window.accounting_subnav.isHidden()
    window._open_accounting_mode('new')
    assert not window.accounting_subnav.isHidden()
    window.close()


def test_workspace_actions_remain_in_viewport_after_narrow_resize(tmp_path, monkeypatch):
    from app.ui.theme import MAIN_STYLE
    from app.ui.accounting_view import AccountingView, SourceView
    from tests.test_accounting_view import record
    window = _window(tmp_path, monkeypatch)
    window.setStyleSheet(MAIN_STYLE)
    window._open_accounting_mode('new')
    module = window._pages_by_id['accounting_automation']
    workspace = module.accounting_workspace
    row = record(issue='Sentetik şube kontrolü')
    workspace.view = AccountingView((SourceView(row.source, 'MANİM Excel', (row,)),))
    workspace.render()
    window.show()
    for width, height in ((1920, 1080), (1366, 768), (1600, 900)):
        window.resize(width, height)
        _APP.processEvents()
        workspace.records.selectRow(0)
        _APP.processEvents()
        assert module.work_scroll.verticalScrollBar().maximum() == 0
        bottom = workspace.output_button.mapTo(window, QPoint(0, workspace.output_button.height()))
        assert bottom.y() <= window.height()
        assert workspace.evidence_scroll.widget().width() <= workspace.evidence_scroll.viewport().width()
        for button in (workspace.attention_tab, workspace.ready_tab, workspace.all_tab):
            assert button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 12
    window.close()


def _window(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1_000)
    monkeypatch.setattr(
        main_window,
        "APP_PATHS",
        SimpleNamespace(
            state_dir=tmp_path / "state",
            assets_dir=Path(__file__).resolve().parents[1] / "assets",
        ),
    )
    store = IdentityStore(tmp_path / "identity.sqlite3")
    session = store.create_initial_admin(
        "Synthetic Company", "admin", "Synthetic Administrator", "Guvenli1234",
    )
    return main_window.MainWindow(session, store)


def test_product_registry_contains_full_product_family_in_navigation_order():
    assert [module.module_id for module in PRODUCT_MODULES] == [
        "dashboard", "accounting_automation", "tax_automation", "banking",
        "einvoice", "reconciliation", "integrations", "operations", "reports", "settings",
    ]
    assert [group for group, _items in grouped_product_modules()] == [
        "ANA KONTROL", "MUHASEBE", "VERGİ", "FİNANS MODÜLLERİ", "PLATFORM", "YÖNETİM",
    ]


def test_module_statuses_have_distinct_textual_presentations():
    expected = {
        ACTIVE: "Aktif",
        LOCKED: "Ek modül",
        UNCONFIGURED: "Kurulum gerekli",
        COMING_SOON: "Yakında",
    }
    for state, label in expected.items():
        badge = ModuleStatusBadge(state)
        assert badge.text() == label
        assert label in badge.accessibleName()


def test_shell_renders_full_product_navigation_and_preserves_legacy_targets(
    tmp_path, monkeypatch,
):
    window = _window(tmp_path, monkeypatch)

    assert [item_id for item_id, _label in window.nav_items] == [
        module.module_id for module in PRODUCT_MODULES
    ]
    assert window.product_module_states["accounting_automation"] == ACTIVE
    assert window.product_module_states["banking"] == UNCONFIGURED
    assert window.product_module_states["einvoice"] == LOCKED
    assert window.product_module_states["tax_automation"] == COMING_SOON
    for page_id in ("manim_transfer", "report_editing", "bank_reconciliation", "operations_center", "history"):
        assert page_id in window._pages_by_id
    window.navigate_to("reconciliation")
    assert window.pages.currentWidget().module.module_id == "reconciliation"
    window.close()


def test_selecting_shell_module_does_not_mutate_operation_history(tmp_path, monkeypatch):
    window = _window(tmp_path, monkeypatch)
    before = tuple((record.id, record.status) for record in window.history.recent(None))

    window.navigate_to("accounting_automation")
    window.navigate_to("banking")
    window.navigate_to("einvoice")
    window.navigate_to("operations")

    after = tuple((record.id, record.status) for record in window.history.recent(None))
    assert after == before
    window.close()


def test_status_badge_exposes_text_instead_of_colour_only():
    badge = StatusBadge("Kontrol gerekiyor", tone="warning")
    assert badge.text() == "Kontrol gerekiyor"
    assert badge.accessibleName() == "Durum: Kontrol gerekiyor"


def test_sidebar_keeps_every_module_name_and_state_in_one_inline_row(
    tmp_path, monkeypatch,
):
    window = _window(tmp_path, monkeypatch)

    assert isinstance(window.sidebar_navigation_scroll, QScrollArea)
    assert window.sidebar.layout().indexOf(window.sidebar_navigation_scroll) < (
        window.sidebar.layout().indexOf(window.sidebar_user_card)
    )
    assert len(window.nav_item_widgets) == len(PRODUCT_MODULES)

    for definition, item in zip(PRODUCT_MODULES, window.nav_item_widgets):
        assert isinstance(item.layout(), QGridLayout)
        assert item.button.text() == definition.display_name
        assert item.button.accessibleName() == definition.display_name
        assert item.status.state == window.product_module_states[definition.module_id]
        assert item.status.parentWidget() is item
        assert item.status.text()
        assert item.layout().indexOf(item.button) < item.layout().indexOf(item.status)

    assert [item.button.text() for item in window.nav_item_widgets if item.button.text()] == [
        module.display_name for module in PRODUCT_MODULES
    ]
    window.close()


def test_sidebar_compact_layout_preserves_navigation_and_bottom_account_area(
    tmp_path, monkeypatch,
):
    window = _window(tmp_path, monkeypatch)

    for width, height in ((1366, 768), (1600, 900), (1920, 1080), (1024, 680)):
        window.resize(width, height)
        window.show()
        _APP.processEvents()
        QTest.qWait(50)
        # Windows can constrain oversized requests to the physical display.
        assert window.minimumWidth() <= window.width() <= width
        assert window.minimumHeight() <= window.height() <= height
        assert window.sidebar_user_card.parentWidget() is window.sidebar
        assert window.sidebar_user_card.isVisibleTo(window)
        assert window.sidebar_navigation_scroll.widget() is not None
        assert all(item.button.accessibleName() for item in window.nav_item_widgets)
        assert window.sidebar.width() == main_window.SIDEBAR_EXPANDED_WIDTH
        assert window.sidebar_navigation_scroll.verticalScrollBar().width() <= 6
        for item in window.nav_item_widgets:
            # Settings intentionally lives beside the profile and its legacy
            # sidebar item stays hidden for navigation/index compatibility.
            # Hidden Qt widgets are not laid out and may retain the default
            # 640x480 geometry, so only visible navigation rows participate in
            # the viewport-geometry assertion.
            if item.isHidden():
                continue
            assert item.status.width() >= item.status.sizeHint().width()
            assert item.button.width() >= item.button.minimumSizeHint().width()
            assert item.status.geometry().right() < item.width()
            viewport = window.sidebar_navigation_scroll.viewport()
            assert item.mapTo(viewport, item.rect().topRight()).x() < viewport.width()
        assert window.sidebar_user_card.geometry().bottom() < window.sidebar.height()

    window.navigate_to("banking")
    assert window.pages.currentWidget().module.module_id == "banking"
    window.navigate_to("einvoice")
    assert window.pages.currentWidget().module.module_id == "einvoice"
    window.close()


def test_shell_exposes_company_in_topbar_and_keeps_bottom_profile_compact(tmp_path, monkeypatch):
    window = _window(tmp_path, monkeypatch)

    assert window.topbar_company_label.text() == "Synthetic Company"
    assert window.topbar_company_label.toolTip() == "Synthetic Company"
    assert window.user_name_label.text() == "Synthetic Administrator"
    assert "Synthetic Company" not in window.user_status_label.text()
    assert window._central_status_label.isHidden()
    assert window.logout_button.toolTip() == "Çıkış yap"
    window.close()


def test_accounting_sources_navigation_uses_integrated_source_preparation(tmp_path, monkeypatch):
    window = _window(tmp_path, monkeypatch)
    page = window._pages_by_id["accounting_automation"]
    tabs = page.tabs
    assert tabs.count() >= 3

    window._open_accounting_mode("sources")
    assert tabs.currentIndex() == 2
    source_page = tabs.currentWidget()
    labels = [label.text() for label in source_page.findChildren(QLabel)]
    assert "Kaynaklar" in labels
    assert "Ham FOM kaynakları" in labels
    assert "FOM Rapor Düzenleme" not in labels

    page.accounting_workspace.source_tools_requested.emit()
    _APP.processEvents()
    assert tabs.currentIndex() == 2

    window.navigate_to("reports")
    reports_page = window.pages.currentWidget()
    report_labels = [label.text() for label in reports_page.findChildren(QLabel)]
    assert "FOM Rapor Motoru" not in report_labels
    assert "Rapor standardizasyonu" not in report_labels
    window.close()
