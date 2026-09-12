from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.operation_history import (
    ERP_REJECTION_REASONS,
    ERP_REJECTION_REASON_LABELS,
    OperationHistory,
)
from app.core.erp_acceptance_target import erp_output_candidates, output_choice_labels
from app.core.output_evidence import verify_output_evidence
from app.core.operation_trends import build_operation_trend_summary, filter_operation_records
from app.ui.common import add_page_header


class HistoryPage(QWidget):
    def __init__(
        self,
        history: OperationHistory,
        *,
        can_record_external_acceptance: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.history = history
        self.can_record_external_acceptance = bool(can_record_external_acceptance)
        self._records = []
        self._all_records = []
        self._events_by_operation: dict[int, list] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setMinimumHeight(620)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)

        add_page_header(
            layout,
            "Geçmiş İşlemler",
            "MANİM Aktarma ve FOM Rapor Düzenleme modüllerinde tamamlanan işlemleri, durumları ve çıktı klasörlerini görüntüleyin.",
        )

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel("İşlem kayıtları")
        title.setObjectName("cardTitle")
        subtitle = QLabel("Firmanızın yerel işlem geçmişi · Dönem ve sonuçlara göre inceleyin.")
        subtitle.setObjectName("cardSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col, 1)

        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)

        self.detail_button = QPushButton("Ayrıntıları göster")
        self.detail_button.setObjectName("secondary")
        self.detail_button.setEnabled(False)
        self.detail_button.clicked.connect(self.show_selected_details)
        header.addWidget(self.detail_button)

        self.acceptance_button = QPushButton("Aktarım sonucunu kaydet")
        self.acceptance_button.setObjectName("secondary")
        self.acceptance_button.setEnabled(False)
        self.acceptance_button.clicked.connect(self.record_external_acceptance)
        header.addWidget(self.acceptance_button)

        self.open_button = QPushButton("Çıktı klasörünü aç")
        self.open_button.setObjectName("primary")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected_output)
        header.addWidget(self.open_button)
        card_layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.period_filter = QComboBox()
        self.period_filter.addItem("Tüm zamanlar", None)
        self.period_filter.addItem("Son 7 gün", 7)
        self.period_filter.addItem("Son 30 gün", 30)
        self.period_filter.addItem("Son 90 gün", 90)
        self.outcome_filter = QComboBox()
        self.outcome_filter.addItem("Tüm karar sonuçları", "")
        self.region_filter = QComboBox()
        self.region_filter.addItem("Tüm bölgeler", "")
        self.bank_filter = QComboBox()
        self.bank_filter.addItem("Tüm bankalar", "")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("İşlem, kullanıcı veya kural ara")
        self.search_input.setClearButtonEnabled(True)
        for widget in (self.period_filter, self.outcome_filter, self.region_filter, self.bank_filter):
            widget.currentIndexChanged.connect(self._render_records)
            filters.addWidget(widget)
        self.search_input.textChanged.connect(self._render_records)
        filters.addWidget(self.search_input, 1)
        card_layout.addLayout(filters)

        self.decision_summary = QLabel()
        self.decision_summary.setObjectName("cardSubtitle")
        self.decision_summary.setWordWrap(True)
        card_layout.addWidget(self.decision_summary)

        self.trend_summary = QLabel()
        self.trend_summary.setObjectName("miniInfoText")
        self.trend_summary.setWordWrap(True)
        card_layout.addWidget(self.trend_summary)

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "Kullanıcı", "Modül", "Durum", "Girdi", "Çıktı", "Karar", "Özet"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 155)
        self.table.setColumnWidth(3, 90)
        self.table.setColumnWidth(4, 70)
        self.table.setColumnWidth(5, 70)
        self.table.setColumnWidth(6, 80)
        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("softPanel")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_title = QLabel("İşlem ayrıntısı")
        detail_title.setObjectName("cardTitle")
        self.detail_text = QLabel("Bir satır seçin; işlem özeti ve güvenli sonraki adım burada görünür.")
        self.detail_text.setObjectName("cardSubtitle")
        self.detail_text.setWordWrap(True)
        detail_layout.addWidget(detail_title)
        detail_layout.addWidget(self.detail_text)
        detail_layout.addStretch(1)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 300])
        card_layout.addWidget(splitter, 1)

        self.selection_hint = QLabel("Bir işlem seçtiğinizde güvenli sonraki adım burada görünür.")
        self.selection_hint.setObjectName("miniInfoText")
        self.selection_hint.setWordWrap(True)
        card_layout.addWidget(self.selection_hint)

        layout.addWidget(card, 1)
        scroll.setWidget(content)
        root.addWidget(scroll)

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%d.%m.%Y %H:%M")
        except Exception:
            return value

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "SUCCESS": "Başarılı",
            "PARTIAL": "Kısmi",
            "FAILED": "Hatalı",
            "RUNNING": "Devam ediyor",
            "INTERRUPTED": "Yarım kaldı",
        }.get(status, status)

    @staticmethod
    def _summary_text(summary: dict) -> str:
        if not summary:
            return "-"
        preferred = [
            ("produced_netsis_records", "Netsis"),
            ("unresolved", "İnceleme"),
            ("customer_rows", "Müşteri"),
            ("sales_rows", "Satış"),
            ("collection_rows", "Tahsilat"),
            ("created_file_count", "Dosya"),
            ("output_integrity", "Bütünlük"),
            ("financial_movement_count", "Finansal kayıt"),
            ("bolge", "Bölge"),
            ("banka_adi", "Banka"),
            ("islem_sayisi", "İşlem"),
            ("durum", "Durum"),
        ]
        parts = [
            f"{label}: {summary[key]}"
            for key, label in preferred
            if key in summary
        ]
        return " • ".join(parts) or "-"

    def refresh(self) -> None:
        self._all_records = self.history.recent(None)
        self._events_by_operation = {
            record.id: self.history.events(record.id)
            for record in self._all_records
        }
        self._populate_decision_filters()
        self._render_records()

    def _populate_decision_filters(self) -> None:
        decisions = [
            event.details
            for events in self._events_by_operation.values()
            for event in events
            if event.code == "DECISION_AUDIT"
        ]
        self._replace_filter_items(
            self.outcome_filter,
            "Tüm karar sonuçları",
            sorted({str(item.get("outcome", "")).strip() for item in decisions if item.get("outcome")}),
            self._outcome_text,
        )
        self._replace_filter_items(
            self.region_filter,
            "Tüm bölgeler",
            sorted({str(item.get("region", "")).strip() for item in decisions if item.get("region")}),
            lambda value: value,
        )
        self._replace_filter_items(
            self.bank_filter,
            "Tüm bankalar",
            sorted({str(item.get("bank", "")).strip() for item in decisions if item.get("bank")}),
            lambda value: value,
        )
        outcomes = [str(item.get("outcome", "")) for item in decisions]
        summary = [f"Karar kaydı: {len(decisions)}"]
        for outcome in (
            "REVIEW",
            "SKIPPED",
            "HAVALE",
            "ODEME_ONAYLANDI",
            "REFERANSLI",
            "SAME_BANK_VIRMAN",
        ):
            count = outcomes.count(outcome)
            if count:
                summary.append(f"{self._outcome_text(outcome)}: {count}")
        self.decision_summary.setText(" • ".join(summary) if decisions else "Bu ekrandaki işlemlerde henüz karar günlüğü bulunmuyor.")

    @staticmethod
    def _replace_filter_items(combo: QComboBox, default_text: str, values: list[str], label) -> None:
        selected = str(combo.currentData() or "")
        blocker = QSignalBlocker(combo)
        combo.clear()
        combo.addItem(default_text, "")
        for value in values:
            combo.addItem(label(value), value)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        del blocker

    @staticmethod
    def _outcome_text(outcome: str) -> str:
        return {
            "HAVALE": "Havale",
            "ODEME_ONAYLANDI": "Ödeme Onaylandı",
            "REFERANSLI": "Referanslı",
            "SAME_BANK_VIRMAN": "Aynı banka virmanı",
            "KURAL_CALISTI": "Kural çalıştı",
            "REVIEW": "İnceleme",
            "SKIPPED": "İncelemede bırakıldı",
        }.get(str(outcome), str(outcome) or "-")

    def _render_records(self) -> None:
        period_days = self.period_filter.currentData()
        period_days = int(period_days) if period_days is not None else None
        outcome = str(self.outcome_filter.currentData() or "")
        region = str(self.region_filter.currentData() or "")
        bank = str(self.bank_filter.currentData() or "")
        needle = self.search_input.text().strip().casefold()

        def matches(record) -> bool:
            decisions = [
                event.details for event in self._events_by_operation.get(record.id, [])
                if event.code == "DECISION_AUDIT"
            ]
            if outcome and not any(str(item.get("outcome", "")) == outcome for item in decisions):
                return False
            if region and not any(str(item.get("region", "")) == region for item in decisions):
                return False
            if bank and not any(str(item.get("bank", "")) == bank for item in decisions):
                return False
            if not needle:
                return True
            searchable = [record.module_name, record.actor, record.status]
            for item in decisions:
                searchable.extend(
                    str(item.get(key, ""))
                    for key in ("outcome", "region", "bank", "rule_code", "reason")
                )
            return needle in " ".join(searchable).casefold()

        period_records = filter_operation_records(self._all_records, period_days=period_days)
        self._records = [record for record in period_records if matches(record)]
        trends = build_operation_trend_summary(self._records)
        period_text = self.period_filter.currentText()
        self.trend_summary.setText(
            f"{period_text}: {trends.operation_count} işlem • Başarılı: {trends.successful_count} • "
            f"Kısmi: {trends.partial_count} • Hatalı/yarım: {trends.failed_count} • "
            f"Netsis kabul/ret: {trends.netsis_accepted}/{trends.netsis_rejected} • "
            f"Psoft kabul/ret: {trends.psoft_accepted}/{trends.psoft_rejected}"
            f"{self._rejection_reason_text(trends.netsis_rejection_reasons, 'Netsis')}"
            f"{self._rejection_reason_text(trends.psoft_rejection_reasons, 'Psoft')}"
        )
        self.table.setRowCount(len(self._records))
        for row_index, record in enumerate(self._records):
            decision_count = sum(
                event.code == "DECISION_AUDIT"
                for event in self._events_by_operation.get(record.id, [])
            )
            values = [
                self._display_date(record.started_at),
                record.actor or "-",
                record.module_name,
                self._status_text(record.status),
                str(len(record.input_files)),
                str(len(record.output_files)),
                str(decision_count),
                self._summary_text(record.summary),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (3, 4, 5, 6):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column, item)
        self._update_actions()

    @staticmethod
    def _rejection_reason_text(reasons: tuple[tuple[str, int], ...], system: str) -> str:
        if not reasons:
            return ""
        labels = [
            f"{ERP_REJECTION_REASON_LABELS.get(code, code)}: {count}"
            for code, count in reasons[:2]
        ]
        return f" • {system} ret nedenleri: {', '.join(labels)}"

    def _update_actions(self) -> None:
        row = self.table.currentRow()
        enabled = (
            0 <= row < len(self._records)
            and bool(self._records[row].output_files)
        )
        self.open_button.setEnabled(enabled)
        self.detail_button.setEnabled(0 <= row < len(self._records))
        record = self._records[row] if 0 <= row < len(self._records) else None
        self.acceptance_button.setEnabled(
            self.can_record_external_acceptance
            and bool(record)
            and record.status in {"SUCCESS", "PARTIAL"}
            and bool(record.output_files)
            and bool(self._acceptance_system(record))
        )
        if record is None:
            self.selection_hint.setText("Bir işlem seçtiğinizde güvenli sonraki adım burada görünür.")
            self.detail_text.setText("Bir satır seçin; işlem özeti ve güvenli sonraki adım burada görünür.")
            return
        status = self._status_text(record.status)
        output_text = f"{len(record.output_files)} çıktı" if record.output_files else "çıktı yok"
        next_step = "Ayrıntıları gösterin; ardından dış sistem kabulünü kaydedin." if record.output_files else "Ayrıntıları açıp hata günlüğünü inceleyin."
        self.selection_hint.setText(f"Seçili işlem: {record.module_name} · {status} · {output_text}. {next_step}")
        summary = self._summary_text(record.summary)
        files = ", ".join(Path(path).name for path in record.output_files[:3]) if record.output_files else "Çıktı yok"
        if len(record.output_files) > 3:
            files += f" (+{len(record.output_files) - 3})"
        self.detail_text.setText(
            f"<b>{record.module_name}</b><br>"
            f"Durum: {status}<br>"
            f"Başlangıç: {self._display_date(record.started_at)}<br>"
            f"Özet: {summary}<br><br>"
            f"Çıktılar: {files}<br><br>{next_step}"
        )

    @staticmethod
    def _acceptance_system(record) -> str:
        return {
            "manim_transfer": "NETSIS",
            "report_editing": "PSOFT",
        }.get(record.module_id, "")

    def record_external_acceptance(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._records)):
            return
        record = self._records[row]
        system = self._acceptance_system(record)
        if not system:
            return
        label = "Netsis" if system == "NETSIS" else "Psoft"
        output_file = self._select_external_output(record, system, label)
        if not output_file:
            return
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Dış aktarım sonucu")
        prompt.setIcon(QMessageBox.Question)
        prompt.setText(f"{label} aktarımı bu çıktı için kabul edildi mi?")
        prompt.setInformativeText(
            "Bu seçim yalnız işlem geçmişine denetim sonucu olarak yazılır; "
            "Excel dosyasını veya aktarımı değiştirmez."
        )
        prompt.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        prompt.button(QMessageBox.Yes).setText("Kabul edildi")
        prompt.button(QMessageBox.No).setText("Reddedildi")
        prompt.button(QMessageBox.Cancel).setText("Vazgeç")
        selected = prompt.exec()
        if selected == QMessageBox.Cancel:
            return
        verdict = "ACCEPTED" if selected == QMessageBox.Yes else "REJECTED"
        reason_code = ""
        if verdict == "REJECTED":
            labels = [label for _code, label in ERP_REJECTION_REASONS]
            reason_label, accepted = QInputDialog.getItem(
                self,
                "Ret nedeni",
                f"{label} aktarım ekranında görünen ana hata nedeni:",
                labels,
                0,
                False,
            )
            if not accepted:
                return
            reason_code = next(
                code for code, item_label in ERP_REJECTION_REASONS if item_label == reason_label
            )
        try:
            self.history.record_external_acceptance(
                record.id,
                system=system,
                verdict=verdict,
                reason_code=reason_code,
                output_file=output_file,
            )
        except Exception as error:
            QMessageBox.warning(self, "Sonuç kaydedilemedi", str(error))
            return
        QMessageBox.information(
            self,
            "Aktarım sonucu kaydedildi",
            f"{label} aktarımı için {'kabul' if verdict == 'ACCEPTED' else 'ret'} sonucu işlem geçmişine eklendi.",
        )
        self.refresh()

    def _select_external_output(self, record, system: str, label: str) -> str | None:
        candidates = erp_output_candidates(record.module_id, system, record.output_files)
        if not candidates:
            QMessageBox.warning(
                self,
                "Aktarım çıktısı bulunamadı",
                f"Bu işlemde {label}'e aktarılabilecek onaylı bir çıktı bulunamadı.",
            )
            return None
        if len(candidates) == 1:
            return candidates[0]
        choices = output_choice_labels(candidates)
        selected, accepted = QInputDialog.getItem(
            self,
            f"{label} çıktısı",
            "Sonucunu kaydedeceğiniz dosyayı seçin:",
            list(choices),
            0,
            False,
        )
        return choices.get(selected) if accepted else None

    def show_selected_details(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._records)):
            return
        record = self._records[row]
        events = self.history.events(record.id)
        decision_events = [event for event in events if event.code == "DECISION_AUDIT"]
        evidence_events = [event for event in events if event.code == "OUTPUT_EVIDENCE"]
        acceptances = self.history.external_acceptance(record.id)
        movement_lines = self._financial_movement_lines(
            self.history.financial_movements(record.id)
        )
        decision_lines = self._decision_lines(decision_events)
        evidence_lines = self._evidence_lines(evidence_events)
        configuration_events = [event for event in events if event.code == "CONFIGURATION_CAPTURED"]
        lines = [
            f"İşlem #{record.id}",
            f"Kullanıcı: {record.actor or '-'}",
            f"Modül: {record.module_name}",
            f"Durum: {self._status_text(record.status)}",
            *([f"İşlem ayarları: sürüm {configuration_events[-1].details.get('revision', '-')}"]
              if configuration_events else []),
            "",
            "Girdiler:",
            *[f"  • {path}" for path in record.input_files],
            "",
            "Çıktılar:",
            *([f"  • {path}" for path in record.output_files] or ["  • -"]),
            "",
            "Çıktı bütünlüğü:",
            *(evidence_lines or ["  • Bu eski işlem için bütünlük kaydı yok."]),
            "",
            "Dış aktarım sonucu:",
            *(self._external_acceptance_lines(acceptances) or ["  • Henüz Netsis/Psoft sonucu kaydedilmedi."]),
            "",
            f"Finansal hareket özeti ({len(movement_lines)} grup):",
            *(movement_lines or ["  • Bu işlem için finansal hareket özeti yok."]),
            "",
            f"Karar özeti ({len(decision_events)} kayıt):",
            *(decision_lines or ["  • Bu işlem için yapılandırılmış karar kaydı yok."]),
            "",
            "Olay günlüğü:",
            *[
                f"  • {self._display_date(event.created_at)} [{event.level}] "
                f"{event.code}: {event.message}"
                for event in events
            ],
        ]
        if record.error_message:
            lines.extend(["", f"Hata: {record.error_message}"])

        dialog = QDialog(self)
        dialog.setWindowTitle(f"İşlem ayrıntıları • #{record.id}")
        dialog.resize(820, 560)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines))
        layout.addWidget(text)
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    @staticmethod
    def _decision_lines(events) -> list[str]:
        lines = []
        for event in events:
            details = event.details
            outcome = HistoryPage._outcome_text(str(details.get("outcome", "")))
            region = details.get("region", "-")
            bank = details.get("bank", "-") or "-"
            raw_amount = details.get("amount")
            try:
                amount = f"{float(raw_amount):,.2f}"
            except (TypeError, ValueError):
                amount = "-"
            rule = details.get("rule_code", "-")
            reason = details.get("reason")
            line = f"  • {region} / {bank} — {outcome} — {amount} TL — kural: {rule}"
            if reason:
                line += f" ({reason})"
            lines.append(line)
        return lines

    @staticmethod
    def _evidence_lines(events) -> list[str]:
        if not events:
            return []
        details = events[-1].details
        comparisons = verify_output_evidence(details)
        labels = {
            "VERIFIED": "doğrulandı",
            "CHANGED": "DEĞİŞMİŞ",
            "MISSING": "DOSYA BULUNAMADI",
            "UNREADABLE": "OKUNAMADI",
            "UNSAFE_PATH": "GÜVENSİZ YOL",
            "BASELINE_UNAVAILABLE": "ilk kayıt doğrulanamadı",
        }
        lines = []
        for item in comparisons:
            try:
                size = f"{int(item.get('size')):,} bayt"
            except (TypeError, ValueError):
                size = "boyut bilinmiyor"
            label = labels.get(str(item.get("comparison", "")), "kontrol edilemedi")
            lines.append(f"  • {item.get('name', '-')} — {size} — {label}")
        return lines or ["  • Bu işlemde çıktı dosyası oluşmadı."]

    @staticmethod
    def _financial_movement_lines(movements) -> list[str]:
        grouped: dict[tuple[str, str, str], list] = {}
        for movement in movements:
            key = (movement.outcome, movement.region, movement.bank or "-")
            grouped.setdefault(key, []).append(movement)
        lines = []
        for (outcome, region, bank), items in sorted(grouped.items()):
            total = sum(item.amount for item in items)
            lines.append(
                f"  • {HistoryPage._outcome_text(outcome)} — {region} / {bank} — "
                f"{len(items)} hareket — {total:,.2f} TL"
            )
        return lines

    @staticmethod
    def _external_acceptance_lines(acceptances) -> list[str]:
        latest_by_system = {}
        for acceptance in acceptances:
            latest_by_system[(acceptance.system, acceptance.output_name)] = acceptance
        labels = {"ACCEPTED": "kabul edildi", "REJECTED": "REDDEDİLDİ"}
        systems = {"NETSIS": "Netsis", "PSOFT": "Psoft"}
        return [
            f"  • {systems.get(item.system, item.system)} — "
            + (f"{item.output_name} — " if item.output_name else "")
            + f"{labels.get(item.verdict, item.verdict)}"
            + (f" ({ERP_REJECTION_REASON_LABELS[item.reason_code]})" if item.reason_code in ERP_REJECTION_REASON_LABELS else "")
            + f" — {HistoryPage._display_date(item.created_at)}"
            for item in sorted(
                latest_by_system.values(),
                key=lambda item: (item.system, item.output_name),
            )
        ]

    def open_selected_output(self) -> None:
        row = self.table.currentRow()
        if not (0 <= row < len(self._records)):
            return
        outputs = self._records[row].output_files
        if not outputs:
            return
        first = Path(outputs[0])
        folder = first if first.is_dir() else first.parent
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
