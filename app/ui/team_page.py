from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.identity import (
    AuthenticatedSession,
    CompanyMember,
    IdentityError,
    IdentityStore,
)
from app.ui.common import add_page_header


ROLE_LABELS = {
    "ADMIN": "Yönetici",
    "OPERATOR": "Operatör",
    "APPROVER": "Onay Sorumlusu",
    "AUDITOR": "Denetçi",
}


class NewUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni kullanıcı")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("Örn. Ayşe Yılmaz")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Örn. ayse.yilmaz")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("En az 10 karakter, harf ve rakam")
        self.role = QComboBox()
        for role, label in ROLE_LABELS.items():
            self.role.addItem(label, role)

        form.addRow("Ad soyad", self.display_name)
        form.addRow("Kullanıcı adı", self.username)
        form.addRow("Geçici parola", self.password)
        form.addRow("Rol", self.role)
        layout.addLayout(form)

        help_text = QLabel(
            "Operatör tüm işlem modüllerini kullanır. Onay sorumlusu yalnız "
            "MANİM ve onay akışına erişir. Denetçi kayıtları salt okunur inceler."
        )
        help_text.setObjectName("miniInfoText")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Kullanıcıyı ekle")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class EditAccessDialog(QDialog):
    def __init__(self, member: CompanyMember, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kullanıcı erişimini düzenle")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        identity = QLabel(f"{member.display_name}\n@{member.username}")
        self.role = QComboBox()
        for role, label in ROLE_LABELS.items():
            self.role.addItem(label, role)
        self.role.setCurrentIndex(max(0, self.role.findData(member.role)))
        self.active = QCheckBox("Bu kullanıcı firmaya erişebilsin")
        self.active.setChecked(member.active)

        form.addRow("Kullanıcı", identity)
        form.addRow("Rol", self.role)
        form.addRow("Durum", self.active)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Erişimi kaydet")
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class TeamPage(QWidget):
    """Firma yöneticisinin yerel kullanıcı ve rol yönetim ekranı."""

    def __init__(
        self,
        identity_store: IdentityStore,
        session: AuthenticatedSession,
        parent=None,
    ):
        super().__init__(parent)
        self.identity_store = identity_store
        self.session = session
        self._members: list[CompanyMember] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)
        add_page_header(
            layout,
            "Ekip ve Yetkiler",
            f"{self.session.company_name} çalışma alanına erişen kullanıcıları yönetin.",
        )

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)

        heading_row = QHBoxLayout()
        title = QLabel("Firma kullanıcıları")
        title.setObjectName("cardTitle")
        add_button = QPushButton("+ Yeni kullanıcı")
        add_button.setObjectName("primary")
        add_button.clicked.connect(self._add_user)
        heading_row.addWidget(title)
        heading_row.addStretch(1)
        heading_row.addWidget(add_button)
        card_layout.addLayout(heading_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Ad soyad", "Kullanıcı adı", "Rol", "Durum", "Son giriş"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._edit_selected)
        card_layout.addWidget(self.table, 1)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        edit_button = QPushButton("Rol / erişim düzenle")
        edit_button.setObjectName("secondary")
        edit_button.clicked.connect(self._edit_selected)
        password_button = QPushButton("Parolayı sıfırla")
        password_button.setObjectName("secondary")
        password_button.clicked.connect(self._reset_password)
        action_row.addWidget(edit_button)
        action_row.addWidget(password_button)
        card_layout.addLayout(action_row)
        layout.addWidget(card, 1)

    def refresh(self) -> None:
        self._members = self.identity_store.members(self.session)
        self.table.setRowCount(len(self._members))
        for row, member in enumerate(self._members):
            values = [
                member.display_name,
                member.username,
                ROLE_LABELS.get(member.role, member.role),
                "Aktif" if member.active else "Erişim kapalı",
                member.last_login_at or "Henüz giriş yapmadı",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (2, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()

    def _selected_member(self) -> CompanyMember | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._members):
            QMessageBox.information(self, "Kullanıcı seçin", "Önce bir kullanıcı seçin.")
            return None
        return self._members[row]

    def _add_user(self) -> None:
        dialog = NewUserDialog(self)
        if not dialog.exec():
            return
        try:
            self.identity_store.create_user(
                self.session,
                username=dialog.username.text(),
                display_name=dialog.display_name.text(),
                password=dialog.password.text(),
                role=str(dialog.role.currentData()),
            )
        except IdentityError as error:
            QMessageBox.warning(self, "Kullanıcı eklenemedi", str(error))
            return
        self.refresh()
        QMessageBox.information(self, "Kullanıcı eklendi", "Yeni kullanıcı erişime açıldı.")

    def _edit_selected(self, *_args) -> None:
        member = self._selected_member()
        if member is None:
            return
        dialog = EditAccessDialog(member, self)
        if not dialog.exec():
            return
        try:
            self.identity_store.update_member(
                self.session,
                member.user_id,
                role=str(dialog.role.currentData()),
                active=dialog.active.isChecked(),
            )
        except IdentityError as error:
            QMessageBox.warning(self, "Erişim kaydedilemedi", str(error))
            return
        self.refresh()

    def _reset_password(self) -> None:
        member = self._selected_member()
        if member is None:
            return
        password, accepted = QInputDialog.getText(
            self,
            "Parolayı sıfırla",
            f"{member.display_name} için yeni parola:",
            QLineEdit.Password,
        )
        if not accepted:
            return
        try:
            self.identity_store.reset_password(self.session, member.user_id, password)
        except IdentityError as error:
            QMessageBox.warning(self, "Parola değiştirilemedi", str(error))
            return
        QMessageBox.information(self, "Parola değiştirildi", "Yeni parola kaydedildi.")
