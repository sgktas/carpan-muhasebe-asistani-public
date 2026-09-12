"""Team task board; all actions go through the authenticated workflow service."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QPlainTextEdit, QTableWidget, QTableWidgetItem, QVBoxLayout, QFileDialog)
from app.core.review_workflow import ReviewWorkflow, PHASE_LABELS, DECISIONS

ACTION_LABELS = {"claim": "Üzerime al", "start": "İncelemeye başla", "submit": "Onaya gönder",
                 "approve": "Onayla", "reject": "Düzeltmeye iade et", "assign": "Ekip üyesine ata", "reopen": "Yeniden aç"}


class ReviewBoard(QFrame):
    def __init__(self, workflow: ReviewWorkflow | None, parent=None):
        super().__init__(parent)
        self.workflow = workflow
        self.tasks, self.visible_tasks, self.names = [], [], {}
        self.setObjectName("surfaceCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        title = QLabel("Ekip görevleri ve onaylar")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        hint = QLabel("Görevi sahiplenin, inceleyin ve kararınızı onaya gönderin. Onay, görev kararını kaydeder; Netsis/Psoft kabulü ayrıca izlenir.")
        hint.setWordWrap(True)
        hint.setObjectName("cardSubtitle")
        layout.addWidget(hint)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("planNotice")
        layout.addWidget(self.summary)
        filters = QGridLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Bölge, banka veya sorumlu ara…")
        self.search.setAccessibleName("Görevlerde ara")
        self.phase = QComboBox()
        self.phase.addItem("Açık görevler", "active")
        self.phase.addItem("Tüm görevler", "all")
        for code, label in PHASE_LABELS.items():
            self.phase.addItem(label, code)
        self.scope = QComboBox()
        for label, code in [("Tüm sorumlular", "all"), ("Benim görevlerim", "mine"), ("Atanmamış", "unassigned"), ("Geciken görevler", "overdue")]:
            self.scope.addItem(label, code)
        self.phase.setAccessibleName("Görev durumu")
        self.scope.setAccessibleName("Görev sorumlusu")
        filters.addWidget(self.search, 0, 0, 1, 2)
        filters.addWidget(self.phase, 1, 0)
        filters.addWidget(self.scope, 1, 1)
        layout.addLayout(filters)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Durum", "Sorumlu", "Bölge / Banka", "Hareket", "Toplam", "Hedef", "Güncelleme"])
        self.table.setObjectName("historyTable")
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(260)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(2, 210)
        self.table.setColumnWidth(4, 130)
        layout.addWidget(self.table)
        self.empty = QLabel("Henüz görev yok. MANİM inceleme kayıtları burada görünecek.")
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        actions = QGridLayout()
        self.action = QComboBox()
        self.execute = QPushButton("Uygula")
        self.execute.setObjectName("primary")
        self.detail = QPushButton("Hareketler ve karar geçmişi")
        self.detail.setObjectName("secondary")
        self.verify = QPushButton("Kaynak dosyaları doğrula")
        self.verify.setObjectName("secondary")
        self.refresh_button = QPushButton("Yenile")
        self.refresh_button.setObjectName("secondary")
        actions.addWidget(self.action, 0, 0)
        actions.addWidget(self.execute, 0, 1)
        actions.addWidget(self.refresh_button, 0, 2)
        actions.addWidget(self.detail, 1, 0, 1, 2)
        actions.addWidget(self.verify, 1, 2)
        layout.addLayout(actions)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.PlainText)
        layout.addWidget(self.message)
        self.table.itemSelectionChanged.connect(self._actions)
        self.table.cellDoubleClicked.connect(lambda *_: self.show_detail())
        self.execute.clicked.connect(self.perform)
        self.detail.clicked.connect(self.show_detail)
        self.verify.clicked.connect(self.verify_sources)
        self.refresh_button.clicked.connect(self.refresh)
        self.search.textChanged.connect(self.render)
        self.phase.currentIndexChanged.connect(self.render)
        self.scope.currentIndexChanged.connect(self.render)

    def refresh(self):
        try:
            self.tasks = self.workflow.list() if self.workflow else []
            self.names = {m.user_id: m.display_name for m in self.workflow.identity.review_members(self.workflow.session)} if self.workflow else {}
            self.message.setText("" if self.workflow else "Görev işlemleri için firma oturumu gerekli.")
        except Exception as error:
            self.tasks = []
            self.message.setText(str(error))
        self.render()

    def selected(self):
        row = self.table.currentRow()
        return self.visible_tasks[row] if 0 <= row < len(self.visible_tasks) else None

    def render(self):
        selected = self.selected()
        selected_id = selected.group.group_id if selected else None
        needle, phase, scope = self.search.text().strip().casefold(), self.phase.currentData(), self.scope.currentData()
        uid = self.workflow.session.user_id if self.workflow else None
        active = [t for t in self.tasks if t.phase not in {"APPROVED", "CANCELLED"}]
        self.summary.setText(f"{len(active)} açık görev · {sum(t.group.assigned_user_id == uid for t in active)} benim görevim · {sum(t.phase == 'PENDING_APPROVAL' for t in active)} onay bekliyor · {sum(t.overdue for t in active)} geciken")
        self.visible_tasks = [t for t in self.tasks if
            (phase == "all" or phase == "active" and t in active or phase == t.phase)
            and (scope == "all" or scope == "mine" and t.group.assigned_user_id == uid or scope == "unassigned" and t.group.assigned_user_id is None or scope == "overdue" and t.overdue)
            and (not needle or needle in (" ".join(m.region + " " + m.bank for m in t.group.members) + " " + self.names.get(t.group.assigned_user_id, "")).casefold())]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.visible_tasks))
        for row, task in enumerate(self.visible_tasks):
            group = task.group
            values = [PHASE_LABELS[task.phase], self.names.get(group.assigned_user_id, "Atanmadı" if group.assigned_user_id is None else "Erişimi kapalı üye"),
                      ", ".join(sorted({m.region + " / " + m.bank for m in group.members})), str(len(group.members)), f"{group.total_amount:,.2f} TL",
                      ("Gecikti · " if task.overdue else "") + self.date(task.due_at), self.date(group.updated_at)]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(row, col, item)
            if group.group_id == selected_id:
                self.table.selectRow(row)
        self.table.blockSignals(False)
        self.empty.setVisible(not self.visible_tasks)
        self._actions()

    def _actions(self):
        task = self.selected()
        self.action.clear()
        try:
            if task and self.workflow:
                for code, label in ACTION_LABELS.items():
                    if self.workflow.allowed(task, code):
                        self.action.addItem(label, code)
        except Exception as error:
            self.message.setText(str(error))
        self.execute.setEnabled(self.action.count() > 0)
        self.detail.setEnabled(task is not None)
        self.verify.setEnabled(task is not None)

    def perform(self):
        task, action = self.selected(), self.action.currentData()
        if not task or not action:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(ACTION_LABELS[action])
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        target, deadline, decision = QComboBox(), QComboBox(), QComboBox()
        if action == "assign":
            try:
                members = self.workflow.assignees(task)
            except Exception as error:
                self.refresh()
                self.message.setText(str(error))
                return
            for member in members:
                target.addItem(member.display_name, member.user_id)
            for label, days in [("Hedef tarih yok", None), ("1 gün içinde", 1), ("3 gün içinde", 3), ("7 gün içinde", 7)]:
                deadline.addItem(label, days)
            form.addRow("Sorumlu", target)
            form.addRow("Hedef süre", deadline)
        if action == "submit":
            for code, label in DECISIONS.items():
                decision.addItem(label, code)
            form.addRow("İnceleme sonucu", decision)
        note = QPlainTextEdit()
        note.setMaximumHeight(120)
        note.setPlaceholderText("Kararın gerekçesi ve yapılan kontrol")
        form.addRow("Açıklama", note)
        layout.addLayout(form)
        if action == "approve" and task.submitted_by == self.workflow.session.user_id:
            hint = QLabel("Kendi gönderdiğiniz kararı onaylıyorsunuz. Bu bilgi karar geçmişine kaydedilecek.")
            hint.setWordWrap(True)
            layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText(ACTION_LABELS[action])
        buttons.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        save = buttons.button(QDialogButtonBox.Save)
        def valid_input():
            save.setEnabled((action not in {"submit", "approve", "reject", "reopen"} or bool(note.toPlainText().strip())) and (action != "assign" or target.count() > 0))
        note.textChanged.connect(valid_input)
        valid_input()
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if not dialog.exec():
            return
        try:
            days = deadline.currentData()
            due = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() if days else None
            self.workflow.act(task.group.group_id, action, expected_version=task.group.version,
                              target_user_id=target.currentData(), due_at=due, decision=decision.currentData(), note=note.toPlainText())
        except Exception as error:
            self.refresh()
            self.message.setText(str(error))
            return
        self.refresh()
        self.message.setText(f"{ACTION_LABELS[action]} işlemi kaydedildi.")

    def show_detail(self):
        task = self.selected()
        if not task:
            return
        try:
            events = self.workflow.events(task.group.group_id)
        except Exception as error:
            self.message.setText(str(error))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Görev hareketleri ve karar geçmişi")
        dialog.resize(800, 550)
        layout = QVBoxLayout(dialog)
        details = QPlainTextEdit()
        details.setReadOnly(True)
        lines = [f"{len(task.group.members)} hareket · {task.group.total_amount:,.2f} TL", ""]
        for m in task.group.members:
            lines.append(f"{m.region} / {m.bank} · {m.amount:,.2f} TL · {m.source_file} / {m.sheet_name} / satır {m.source_row}\n{m.reason}")
        lines += ["", "KARAR GEÇMİŞİ"]
        first_version = json.loads(events[0]["payload"])["version"] if events else task.group.version + 1
        for event in self.workflow.queue.events(task.group.group_id):
            if event.new_version < first_version:
                lines.append(f"{self.date(event.created_at)} · Eski kuyruk kaydı · {event.previous_status or 'Yeni kayıt'} → {event.new_status} · sürüm {event.new_version}")
        for event in events:
            p = json.loads(event["payload"])
            lines.append(f"{self.date(event['created_at'])} · {self.names.get(event['actor_user_id'], 'Üye #' + str(event['actor_user_id']))} · {ACTION_LABELS[event['action']]}\n{PHASE_LABELS[p['before']]} → {PHASE_LABELS[p['after']]} · Sorumlu: {self.names.get(p['owner'], 'Atanmadı')}\n{p['note']}")
        if not events:
            lines.append("Bu görevde yeni iş akışı kararı yok; önceki kuyruk kayıtları korunuyor.")
        details.setPlainText("\n".join(lines))
        layout.addWidget(details)
        dialog.exec()

    def verify_sources(self):
        task = self.selected()
        if not task:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Kaynak dosyaları seçin", "", "Excel (*.xlsx *.xls)")
        if paths:
            try:
                current = next((t for t in self.workflow.list() if t.group.group_id == task.group.group_id), None)
                if current is None:
                    raise ValueError("Göreve erişiminiz yok; ekranı yenileyin.")
                valid, message = self.workflow.queue.source_integrity(current.group, {Path(p).name: p for p in paths})
                self.message.setText(message)
            except Exception as error:
                self.refresh()
                self.message.setText(str(error))

    @staticmethod
    def date(value):
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y %H:%M") if value else "—"
