from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollArea
from PySide6.QtTest import QTest

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
        assert isinstance(item.layout(), QHBoxLayout)
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
