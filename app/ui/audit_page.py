from __future__ import annotations

from datetime import datetime
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.identity import AuthenticatedSession, IdentityStore
from app.ui.common import add_page_header


ACTION_LABELS = {
    "INITIAL_ADMIN_CREATED": "İlk yönetici oluşturuldu",
    "LOGIN": "Oturum açma",
    "LOGOUT": "Oturum kapatma",
    "USER_CREATED": "Kullanıcı oluşturuldu",
    "USER_ACCESS_UPDATED": "Kullanıcı erişimi değiştirildi",
    "PASSWORD_RESET": "Parola sıfırlandı",
}


class AuditPage(QWidget):
    """Firma kapsamındaki güvenlik olaylarının salt okunur görünümü."""

    def __init__(
        self,
        identity_store: IdentityStore,
        session: AuthenticatedSession,
        parent=None,
    ):
        super().__init__(parent)
        self.identity_store = identity_store
        self.session = session
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)
        add_page_header(
            layout,
            "Güvenlik Kayıtları",
            "Oturum ve yetki hareketlerini değişiklik algılayan kayıt zincirinden inceleyin.",
        )

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Son güvenlik olayları")
        title.setObjectName("cardTitle")
        self.integrity_label = QLabel()
        self.integrity_label.setObjectName("miniInfoText")
        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.integrity_label)
        header.addWidget(refresh_button)
        card_layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "Kullanıcı No", "Olay", "Sonuç", "Ayrıntı"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        card_layout.addWidget(self.table, 1)
        layout.addWidget(card, 1)

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value

    def refresh(self) -> None:
        events = self.identity_store.audit_events(self.session)
        valid = self.identity_store.audit_chain_is_valid()
        self.integrity_label.setText(
            "Kayıt zinciri doğrulandı" if valid else "DİKKAT: Kayıt zinciri değişmiş"
        )
        self.integrity_label.setStyleSheet(
            "color:#16794B; font-weight:600;"
            if valid
            else "color:#B42318; font-weight:700;"
        )
        self.table.setRowCount(len(events))
        for row, event in enumerate(events):
            values = [
                self._display_date(event.created_at),
                str(event.user_id) if event.user_id is not None else "-",
                ACTION_LABELS.get(event.action, event.action),
                "Başarılı" if event.outcome == "SUCCESS" else event.outcome,
                json.dumps(event.details, ensure_ascii=False, sort_keys=True),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
