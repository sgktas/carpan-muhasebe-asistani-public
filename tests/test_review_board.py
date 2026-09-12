import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtGui import QFontDatabase
from app.core import identity
from app.core.identity import IdentityStore
from app.core.operation_history import OperationHistory
from app.core.review_queue import ReviewMember, ReviewQueue
from app.ui.operation_center_page import OperationCenterPage
from app.ui.theme import MAIN_STYLE

app = QApplication.instance() or QApplication([])
for name in ("segoeui.ttf", "segoeuib.ttf"):
    path = Path("C:/Windows/Fonts") / name
    if path.exists():
        QFontDatabase.addApplicationFont(str(path))


def test_board_filters_allowed_actions_and_full_screen_layout(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1000)
    store = IdentityStore(tmp_path / "identity.db")
    admin = store.create_initial_admin("Demo", "admin", "Demo Yönetici", "Guvenli1234")
    history = OperationHistory(tmp_path / "operations.db", company_id=admin.company_id, user_id=admin.user_id)
    queue = ReviewQueue(history.database_path, company_id=admin.company_id)
    group = queue.enqueue([ReviewMember("demo.xlsx", 1, 147978, "ANTALYA", "GARANTI", "İki havale toplam kontrolü")])
    queue.enqueue([ReviewMember("demo2.xlsx", 2, 23000, "AYDIN", "ZIRAAT", "Tutar farkı")])
    page = OperationCenterPage(history, identity_store=store, session=admin)
    page.setObjectName("mainRoot")
    page.setStyleSheet(MAIN_STYLE)
    board = page.review_board
    assert len(board.tasks) == 2
    board.search.setText("ANTALYA")
    assert board.table.rowCount() == 1
    board.table.selectRow(0)
    assert {board.action.itemData(i) for i in range(board.action.count())} == {"claim", "assign"}
    board.workflow.act(group, "claim", expected_version=1)
    board.refresh()
    board.table.selectRow(0)
    assert "start" in {board.action.itemData(i) for i in range(board.action.count())}
    board.scope.setCurrentIndex(board.scope.findData("mine"))
    assert board.table.rowCount() == 1
    try:
        for width in (760, 1100):
            page.resize(width, 900)
            page.show()
            for _ in range(5):
                app.processEvents()
            assert page.width() == width
            for scroll in page.findChildren(QScrollArea):
                if scroll.isVisible():
                    assert scroll.widget().width() <= scroll.viewport().width()
            folder = os.environ.get("CARPAN_UI_SCREENSHOT_DIR")
            if folder:
                target = Path(folder)
                target.mkdir(parents=True, exist_ok=True)
                page.grab().save(str(target / f"review-board-{width}.png"))
    finally:
        page.close()
        page.deleteLater()


def test_board_does_not_retain_tasks_after_access_revoked(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1000)
    store = IdentityStore(tmp_path / "identity.db")
    admin = store.create_initial_admin("Demo", "admin", "Demo Yönetici", "Guvenli1234")
    uid = store.create_user(admin, username="operator", display_name="Operatör", password="Guvenli1234", role="OPERATOR")
    session = store.authenticate("operator", "Guvenli1234", admin.company_id)
    history = OperationHistory(tmp_path / "operations.db", company_id=session.company_id, user_id=uid)
    ReviewQueue(history.database_path, company_id=session.company_id).enqueue([ReviewMember("demo",1,1,"AYDIN","GARANTI","")])
    page = OperationCenterPage(history, identity_store=store, session=session)
    assert page.review_board.table.rowCount() == 1
    store.update_member(admin, uid, role="OPERATOR", active=False)
    page.review_board.refresh()
    assert page.review_board.table.rowCount() == 0
    assert not page.review_board.execute.isEnabled()
    page.deleteLater()
