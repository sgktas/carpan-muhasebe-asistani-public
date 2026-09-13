from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.operation_center import (
    build_operation_center_snapshot,
    operation_attention_text,
    operation_status_presentation,
)
from app.core.operation_history import (
    ERP_REJECTION_REASON_LABELS,
    ERP_REJECTION_REASONS,
    OperationHistory,
)
from app.core.erp_acceptance_target import (
    aggregate_erp_acceptance,
    erp_output_candidates,
    output_choice_labels,
)
from app.core.operation_simulation import (
    attach_simulation_details,
    simulation_summary_from_payload,
)
from app.core.operation_read_model import OperationReadModel
from app.core.operation_trends import build_operation_trend_summary, filter_operation_records
from app.core.identity import AuthenticatedSession, IdentityError, IdentityStore
from app.core.processed_files_log import ProcessedFilesLog
from app.core.publication_journal import PublicationJournal
from app.core.review_queue import ReviewQueue
from app.core.review_workflow import ReviewWorkflow
from app.ui.review_board import ReviewBoard
from app.ui.simulation_dashboard import SimulationDashboard
from app.ui.common import add_page_header


class OperationCenterPage(QWidget):
    """Yerel işlemlerden türetilen günlük finans operasyon görünümü."""

    safe_manim_retry_requested = Signal(object)

    def __init__(
        self,
        history: OperationHistory,
        *,
        identity_store: IdentityStore | None = None,
        session: AuthenticatedSession | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.history = history
        self.identity_store = identity_store
        self.session = session
        self.review_queue = ReviewQueue(history.database_path, company_id=history.company_id)
        self.publication_journal = PublicationJournal(
            history.database_path.parent / "publication_journal.sqlite3",
            company_id=history.company_id,
        )
        self.review_workflow = (
            ReviewWorkflow(self.review_queue, self.identity_store, self.session)
            if self.identity_store and self.session
            else None
        )
        self.operation_read_model = OperationReadModel(
            history,
            publication_journal=self.publication_journal,
            review_queue=self.review_queue,
            review_workflow=self.review_workflow,
            processed_files=ProcessedFilesLog(
                history.database_path.parent / "processed_files.json"
            ),
        )
        self._attention_records = ()
        self._review_groups = ()
        self._pending_publications = ()
        self._assignment_members = ()
        self._rejected_manim_records = ()
        self._completed_manim_records = ()
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
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(18)
        add_page_header(
            layout,
            "Operasyon Merkezi",
            "Günlük finans işlemlerinin durumunu, inceleme bekleyen kayıtları ve üretilen çıktıları tek yerde takip edin.",
        )

        self._build_consistency_card(layout)

        self.review_board = ReviewBoard(self.review_workflow)
        layout.addWidget(self.review_board)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        self._metric_values: dict[str, QLabel] = {}
        for index, (key, title, subtitle) in enumerate(
            (
                ("total", "Toplam işlem", "Firma işlem geçmişi"),
                ("success", "Başarılı", "Tamamlanan işlemler"),
                ("attention", "Dikkat gerekiyor", "Kısmi, hatalı veya yarım"),
                ("unresolved", "İnceleme kaydı", "Manuel karar bekleyenler"),
                ("files", "Üretilen dosya", "İşlem geçmişindeki çıktılar"),
                ("queue", "Açık inceleme", "Kalıcı kuyruktaki gruplar"),
                ("simulation_ok", "Simülasyon uyumlu", "Planla aynı tamamlanan aktarımlar"),
                ("simulation_warn", "Simülasyon farkı", "Kontrol gerektiren aktarım planları"),
                ("netsis_rejected", "Netsis ret", "Manuel aktarımda reddedilenler"),
                ("psoft_rejected", "Psoft ret", "Manuel aktarımda reddedilenler"),
                ("reconciliation_attention", "Mutabakat farkı", "Nokta atışı kontrol bekleyenler"),
            )
        ):
            metrics.addWidget(self._metric_card(key, title, subtitle), index // 3, index % 3)
        layout.addLayout(metrics)

        weekly_card = QFrame()
        weekly_card.setObjectName("surfaceCard")
        weekly_layout = QVBoxLayout(weekly_card)
        weekly_layout.setContentsMargins(20, 18, 20, 20)
        weekly_layout.setSpacing(12)
        weekly_title = QLabel("Son 7 gün · Operasyon özeti")
        weekly_title.setObjectName("cardTitle")
        weekly_subtitle = QLabel(
            "Yerel işlem geçmişinden oluşur. Banka, müşteri, IBAN veya Excel içeriği gösterilmez ya da merkeze gönderilmez."
        )
        weekly_subtitle.setObjectName("cardSubtitle")
        weekly_subtitle.setWordWrap(True)
        weekly_layout.addWidget(weekly_title)
        weekly_layout.addWidget(weekly_subtitle)
        weekly_metrics = QGridLayout()
        weekly_metrics.setSpacing(12)
        self._weekly_metric_values: dict[str, QLabel] = {}
        for index, (key, title, subtitle) in enumerate(
            (
                ("operations", "İşlem", "Başlatılan operasyon"),
                ("successful", "Tamamlandı", "Başarılı tamamlanan"),
                ("accepted", "ERP kabul", "Netsis/Psoft onaylanan"),
                ("attention", "Kontrol", "Dikkat gerektiren"),
                ("reconciliation", "Mutabakat", "Açık fark veya kayıt"),
            )
        ):
            weekly_metrics.addWidget(self._weekly_metric_card(key, title, subtitle), index // 3, index % 3)
        weekly_layout.addLayout(weekly_metrics)
        layout.addWidget(weekly_card)

        quality_card = QFrame()
        quality_card.setObjectName("surfaceCard")
        quality_layout = QVBoxLayout(quality_card)
        quality_layout.setContentsMargins(20, 18, 20, 20)
        quality_layout.setSpacing(6)
        quality_title = QLabel("ERP kalite sinyali · Son 7 gün")
        quality_title.setObjectName("cardTitle")
        quality_subtitle = QLabel(
            "Tekrarlayan retleri görün; önce ilgili çıktı profilini kontrol edin. Bu alan otomatik düzeltme veya aktarım yapmaz."
        )
        quality_subtitle.setObjectName("cardSubtitle")
        quality_subtitle.setWordWrap(True)
        self.erp_quality_summary = QLabel()
        self.erp_quality_summary.setObjectName("miniInfoText")
        self.erp_quality_summary.setWordWrap(True)
        quality_layout.addWidget(quality_title)
        quality_layout.addWidget(quality_subtitle)
        quality_layout.addWidget(self.erp_quality_summary)
        layout.addWidget(quality_card)

        result_card = QFrame()
        result_card.setObjectName("surfaceCard")
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(20, 18, 20, 20)
        result_layout.setSpacing(12)
        result_header = QHBoxLayout()
        result_title_col = QVBoxLayout()
        result_title = QLabel("Tamamlanan MANİM operasyonu")
        result_title.setObjectName("cardTitle")
        result_subtitle = QLabel(
            "İşlem öncesi banka hareketlerini ve hazırlanan Netsis dağılımını bölge/banka bazında karşılaştırın."
        )
        result_subtitle.setObjectName("cardSubtitle")
        result_subtitle.setWordWrap(True)
        result_title_col.addWidget(result_title)
        result_title_col.addWidget(result_subtitle)
        result_header.addLayout(result_title_col, 1)
        self.operation_result_combo = QComboBox()
        self.operation_result_combo.setMinimumWidth(330)
        self.operation_result_combo.currentIndexChanged.connect(
            self._render_completed_manim_result
        )
        result_header.addWidget(self.operation_result_combo)
        result_layout.addLayout(result_header)
        self.operation_result_context = QLabel()
        self.operation_result_context.setObjectName("cardSubtitle")
        self.operation_result_context.setWordWrap(True)
        result_layout.addWidget(self.operation_result_context)
        self.operation_result_dashboard = SimulationDashboard()
        result_layout.addWidget(self.operation_result_dashboard)
        result_actions = QHBoxLayout()
        result_actions.addStretch(1)
        self.open_operation_result_button = QPushButton("Çıktı Klasörünü Aç")
        self.open_operation_result_button.setObjectName("secondary")
        self.open_operation_result_button.clicked.connect(
            self._open_completed_manim_output
        )
        self.record_operation_result_button = QPushButton("Netsis Sonucunu Kaydet")
        self.record_operation_result_button.setObjectName("primary")
        self.record_operation_result_button.clicked.connect(
            self._record_completed_manim_acceptance
        )
        result_actions.addWidget(self.open_operation_result_button)
        result_actions.addWidget(self.record_operation_result_button)
        result_layout.addLayout(result_actions)
        layout.addWidget(result_card)

        rejection_card = QFrame()
        rejection_card.setObjectName("surfaceCard")
        rejection_layout = QVBoxLayout(rejection_card)
        rejection_layout.setContentsMargins(20, 18, 20, 20)
        rejection_layout.setSpacing(12)
        rejection_title = QLabel("Netsis retleri · güvenli yeniden çalışma")
        rejection_title.setObjectName("cardTitle")
        rejection_subtitle = QLabel(
            "Netsis'in reddettiği MANİM çıktısını ve kayıtlı ana nedeni görün. "
            "Kaynakları yeniden yüklemek yalnız çalışma alanını hazırlar; Excel üretmez ve Netsis'e aktarım yapmaz."
        )
        rejection_subtitle.setObjectName("cardSubtitle")
        rejection_subtitle.setWordWrap(True)
        rejection_layout.addWidget(rejection_title)
        rejection_layout.addWidget(rejection_subtitle)

        self.rejection_table = QTableWidget(0, 5)
        self.rejection_table.setObjectName("historyTable")
        self.rejection_table.setHorizontalHeaderLabels(
            ["Tarih", "İşlem", "Reddedilen çıktı", "Neden", "Kaynak durumu"]
        )
        self.rejection_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.rejection_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.rejection_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.rejection_table.verticalHeader().setVisible(False)
        self.rejection_table.horizontalHeader().setStretchLastSection(True)
        self.rejection_table.setColumnWidth(0, 145)
        self.rejection_table.setColumnWidth(1, 90)
        self.rejection_table.setColumnWidth(2, 300)
        self.rejection_table.setColumnWidth(3, 210)
        rejection_layout.addWidget(self.rejection_table)

        retry_controls = QHBoxLayout()
        retry_controls.setSpacing(8)
        retry_label = QLabel("Yeni çıktı biçimi")
        retry_label.setObjectName("miniInfoTitle")
        self.retry_profile_combo = QComboBox()
        self.retry_profile_combo.addItem("Normal · banka ve bölge ayrı", "netsis")
        self.retry_profile_combo.addItem("Toplu · banka kodlu", "netsis_toplu")
        self.open_rejected_output_button = QPushButton("Reddedilen Çıktıyı Aç")
        self.open_rejected_output_button.setObjectName("secondary")
        self.open_rejected_output_button.clicked.connect(self._open_rejected_output)
        self.prepare_manim_retry_button = QPushButton("Kaynakları MANİM'de Hazırla")
        self.prepare_manim_retry_button.setObjectName("primary")
        self.prepare_manim_retry_button.clicked.connect(self._prepare_manim_retry)
        retry_controls.addWidget(retry_label)
        retry_controls.addWidget(self.retry_profile_combo)
        retry_controls.addStretch(1)
        retry_controls.addWidget(self.open_rejected_output_button)
        retry_controls.addWidget(self.prepare_manim_retry_button)
        rejection_layout.addLayout(retry_controls)
        self.rejection_detail = QLabel("Bir Netsis ret kaydı seçin.")
        self.rejection_detail.setObjectName("cardSubtitle")
        self.rejection_detail.setWordWrap(True)
        rejection_layout.addWidget(self.rejection_detail)
        self.rejection_table.itemSelectionChanged.connect(self._update_rejection_actions)
        layout.addWidget(rejection_card)

        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(12)
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(3)
        title = QLabel("Öncelikli takip listesi")
        title.setObjectName("cardTitle")
        subtitle = QLabel("Bu liste otomatik karar vermez; kontrol edilmesi gereken işlemleri görünür kılar.")
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col, 1)
        refresh_button = QPushButton("Yenile")
        refresh_button.setObjectName("secondary")
        refresh_button.clicked.connect(self.refresh)
        header.addWidget(refresh_button)
        card_layout.addLayout(header)

        filters = QHBoxLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItem("Tüm dikkat kayıtları", "")
        self.status_filter.addItem("Kısmi işlemler", "PARTIAL")
        self.status_filter.addItem("Hatalı işlemler", "FAILED")
        self.status_filter.addItem("Yarım kalanlar", "INTERRUPTED")
        self.status_filter.currentIndexChanged.connect(self._render_attention_records)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Modül, kullanıcı veya kontrol nedeni ara")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._render_attention_records)
        filters.addWidget(self.status_filter)
        filters.addWidget(self.search_input, 1)
        card_layout.addLayout(filters)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("historyTable")
        self.table.setHorizontalHeaderLabels(["Tarih", "Modül", "Durum", "Kontrol nedeni", "Kullanıcı"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 145)
        self.table.setColumnWidth(1, 165)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 440)
        card_layout.addWidget(self.table)
        layout.addWidget(card)

        recovery_card = QFrame()
        recovery_card.setObjectName("surfaceCard")
        recovery_layout = QVBoxLayout(recovery_card)
        recovery_layout.setContentsMargins(20, 18, 20, 20)
        recovery_layout.setSpacing(10)
        recovery_title = QLabel("Yayın ve kurtarma kontrolü")
        recovery_title.setObjectName("cardTitle")
        recovery_subtitle = QLabel(
            "Çıktı klasörü oluştuğu halde işlem tamamlanamadıysa burada görünür. "
            "Kaynağı yeniden işlemek için önce eski çıktının dış sisteme aktarılmadığını kontrol edin."
        )
        recovery_subtitle.setObjectName("cardSubtitle")
        recovery_subtitle.setWordWrap(True)
        recovery_layout.addWidget(recovery_title)
        recovery_layout.addWidget(recovery_subtitle)
        self.recovery_table = QTableWidget(0, 4)
        self.recovery_table.setObjectName("historyTable")
        self.recovery_table.setHorizontalHeaderLabels(["Yayın zamanı", "Kaynak", "Çıktı klasörü", "Durum"])
        self.recovery_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recovery_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recovery_table.setSortingEnabled(True)
        self.recovery_table.setAlternatingRowColors(True)
        self.recovery_table.setWordWrap(False)
        self.recovery_table.verticalHeader().setVisible(False)
        self.recovery_table.horizontalHeader().setStretchLastSection(True)
        self.recovery_table.setColumnWidth(0, 145)
        self.recovery_table.setColumnWidth(1, 90)
        self.recovery_table.setColumnWidth(2, 430)
        recovery_layout.addWidget(self.recovery_table)
        recovery_actions = QHBoxLayout()
        self.open_recovery_output_button = QPushButton("Çıktı Klasörünü Aç")
        self.open_recovery_output_button.setObjectName("secondary")
        self.open_recovery_output_button.clicked.connect(self._open_recovery_output)
        self.approve_retry_button = QPushButton("Yeniden İşlem İçin Onayla")
        self.approve_retry_button.setObjectName("secondary")
        self.approve_retry_button.clicked.connect(self._approve_recovery_retry)
        recovery_actions.addWidget(self.open_recovery_output_button)
        recovery_actions.addWidget(self.approve_retry_button)
        recovery_actions.addStretch(1)
        recovery_layout.addLayout(recovery_actions)
        self.recovery_table.itemSelectionChanged.connect(self._update_recovery_actions)
        layout.addWidget(recovery_card)
        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def _build_consistency_card(self, layout: QVBoxLayout) -> None:
        card = QFrame()
        card.setObjectName("surfaceCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 20)
        card_layout.setSpacing(10)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        title = QLabel("Operasyon tutarlılık görünümü")
        title.setObjectName("cardTitle")
        subtitle = QLabel(
            "Geçmiş, yayın, inceleme ve fiziksel çıktı durumunu tek operasyonda birlikte görün."
        )
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        self.consistency_operation_combo = QComboBox()
        self.consistency_operation_combo.setMinimumWidth(350)
        self.consistency_operation_combo.setAccessibleName(
            "Tutarlılığı incelenecek operasyon"
        )
        self.consistency_operation_combo.currentIndexChanged.connect(
            self._render_operation_consistency
        )
        header.addWidget(self.consistency_operation_combo)
        card_layout.addLayout(header)

        status_row = QHBoxLayout()
        self.consistency_status = QLabel("Operasyon seçin")
        self.consistency_status.setAlignment(Qt.AlignCenter)
        self.consistency_status.setMinimumWidth(190)
        self.consistency_status.setAccessibleName("Operasyon tutarlılık durumu")
        status_row.addWidget(self.consistency_status, 0, Qt.AlignLeft)
        self.consistency_explanation = QLabel()
        self.consistency_explanation.setObjectName("miniInfoText")
        self.consistency_explanation.setWordWrap(True)
        status_row.addWidget(self.consistency_explanation, 1)
        card_layout.addLayout(status_row)

        self.consistency_facts = QLabel()
        self.consistency_facts.setObjectName("softPanel")
        self.consistency_facts.setWordWrap(True)
        self.consistency_facts.setTextFormat(Qt.PlainText)
        self.consistency_facts.setContentsMargins(12, 10, 12, 10)
        card_layout.addWidget(self.consistency_facts)
        self.consistency_reasons = QLabel()
        self.consistency_reasons.setWordWrap(True)
        self.consistency_reasons.setTextFormat(Qt.PlainText)
        card_layout.addWidget(self.consistency_reasons)
        self.consistency_hint = QLabel()
        self.consistency_hint.setObjectName("cardSubtitle")
        self.consistency_hint.setWordWrap(True)
        card_layout.addWidget(self.consistency_hint)
        layout.addWidget(card)

    def _metric_card(self, key: str, title_text: str, subtitle_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("surfaceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 15, 17, 15)
        layout.setSpacing(4)
        title = QLabel(title_text)
        title.setObjectName("miniInfoTitle")
        value = QLabel("0")
        value.setStyleSheet("font-size:28px; font-weight:700; color:#214866;")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("miniInfoText")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(subtitle)
        if key in {"attention", "unresolved", "queue", "reconciliation_attention"}:
            action = QPushButton("İncelemeye git")
            action.setObjectName("ghost")
            action.setCursor(Qt.PointingHandCursor)
            action.clicked.connect(lambda checked=False, target=key: self._focus_metric(target))
            layout.addWidget(action, 0, Qt.AlignLeft)
        card.setToolTip("Bu özetin ayrıntılarını aşağıdaki listede inceleyin.")
        card.setAccessibleName(f"{title_text}: {subtitle_text}")
        self._metric_values[key] = value
        return card

    def _focus_metric(self, key: str) -> None:
        """Özet kartından ilgili dikkat listesini görünür ve odaklı hâle getirir."""
        if key in {"attention", "unresolved", "queue", "reconciliation_attention"}:
            self.status_filter.setCurrentIndex(0)
            self.table.setFocus(Qt.OtherFocusReason)
            self.table.scrollToTop()

    def _weekly_metric_card(self, key: str, title_text: str, subtitle_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("softPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(4)
        title = QLabel(title_text)
        title.setObjectName("miniInfoTitle")
        value = QLabel("0")
        value.setStyleSheet("font-size:24px; font-weight:700; color:#214866;")
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("miniInfoText")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(value)
        layout.addWidget(subtitle)
        self._weekly_metric_values[key] = value
        return card

    def refresh(self) -> None:
        records = self.history.recent(None)
        snapshot = build_operation_center_snapshot(records)
        values = {
            "total": snapshot.total_operations,
            "success": snapshot.successful_operations,
            "attention": snapshot.attention_operations,
            "unresolved": snapshot.unresolved_items,
            "files": snapshot.generated_files,
            "queue": 0,
            "simulation_ok": snapshot.simulation_verified,
            "simulation_warn": snapshot.simulation_mismatches,
            "netsis_rejected": snapshot.netsis_rejections,
            "psoft_rejected": snapshot.psoft_rejections,
            "reconciliation_attention": snapshot.reconciliation_attention,
        }
        for key, value in values.items():
            self._metric_values[key].setText(str(value))
        weekly = snapshot.weekly_summary
        weekly_values = {
            "operations": weekly.operation_count,
            "successful": weekly.successful_count,
            "accepted": weekly.accepted_count,
            "attention": weekly.attention_count,
            "reconciliation": weekly.reconciliation_attention_count,
        }
        for key, value in weekly_values.items():
            self._weekly_metric_values[key].setText(str(value))
        self._render_erp_quality_summary(records)
        self._populate_consistency_operations(records)
        self._attention_records = snapshot.attention_records
        self._completed_manim_records = tuple(
            record
            for record in records
            if record.module_id == "manim_transfer"
            and record.status in {"SUCCESS", "PARTIAL"}
        )[:20]
        self._populate_completed_manim_results()
        self._rejected_manim_records = tuple(
            record
            for record in records
            if record.module_id == "manim_transfer"
            and self._external_acceptance(record).get("verdict") == "REJECTED"
        )
        self._render_rejected_manim_records()
        self.review_board.refresh()
        self._metric_values["queue"].setText(str(sum(t.phase not in {"APPROVED", "CANCELLED"} for t in self.review_board.tasks)))
        self._pending_publications = self.publication_journal.list(status="PUBLISHED")
        self._render_pending_publications()
        self._update_recovery_actions()
        self._render_attention_records()

    def _populate_consistency_operations(self, records) -> None:
        previous_id = self.consistency_operation_combo.currentData()
        self.consistency_operation_combo.blockSignals(True)
        self.consistency_operation_combo.clear()
        for record in records:
            self.consistency_operation_combo.addItem(
                f"#{record.id} · {self._display_date(record.started_at)} · {record.module_name}",
                record.id,
            )
        selected = self.consistency_operation_combo.findData(previous_id)
        self.consistency_operation_combo.setCurrentIndex(
            selected if selected >= 0 else (0 if records else -1)
        )
        self.consistency_operation_combo.blockSignals(False)
        self._render_operation_consistency()

    def _render_operation_consistency(self) -> None:
        operation_id = self.consistency_operation_combo.currentData()
        view = self.operation_read_model.get_operation_view(
            operation_id,
            company_id=self.history.company_id,
        )
        if view is None:
            self.consistency_status.setText("Operasyon yok")
            self.consistency_status.setStyleSheet(self._consistency_chip_style("neutral"))
            self.consistency_explanation.setText(
                "Firma kapsamında görüntülenecek bir operasyon bulunmuyor."
            )
            self.consistency_facts.setText("Geçmiş: Kayıt yok")
            self.consistency_reasons.clear()
            self.consistency_hint.clear()
            return

        presentation = operation_status_presentation(view)
        self.consistency_status.setText(presentation.title)
        self.consistency_status.setProperty("consistencySeverity", presentation.severity)
        self.consistency_status.setStyleSheet(
            self._consistency_chip_style(presentation.severity)
        )
        self.consistency_explanation.setText(presentation.explanation)
        publication = self._publication_status_text(view.publication_status)
        review = (
            f"{view.open_review_group_count} açık grup · "
            f"{view.pending_review_count} kayıt"
            if view.open_review_group_count
            else "Açık kayıt yok"
        )
        phases = sorted(
            {item.phase for item in view.reviews if item.phase is not None}
        )
        if phases:
            review += " · " + ", ".join(
                self._review_phase_text(phase) for phase in phases
            )
        self.consistency_facts.setText(
            " · ".join((
                f"Geçmiş: {self._history_status_text(view.history_status)}",
                f"Yayın: {publication}",
                f"İnceleme: {review}",
                f"Çıktı: {self._output_presence_text(view.output_presence_state)}",
                f"Kaynak kaydı: {self._processed_source_text(view.processed_source_state)}",
            ))
        )
        self.consistency_reasons.setText(
            "\n".join(f"• {reason}" for reason in presentation.reason_texts)
            if presentation.reason_texts
            else "Kontrol nedeni bulunmuyor."
        )
        self.consistency_hint.setText(presentation.action_hint)

    @staticmethod
    def _consistency_chip_style(severity: str) -> str:
        colors = {
            "success": ("#E7F6EC", "#187A43", "#B7DFC7"),
            "warning": ("#FFF4DF", "#9A5A00", "#EBCB91"),
            "critical": ("#FDECEC", "#A12A2A", "#E9B5B5"),
            "neutral": ("#EEF3F7", "#456273", "#CEDAE2"),
        }
        background, foreground, border = colors.get(severity, colors["neutral"])
        return (
            "QLabel {"
            f"background:{background}; color:{foreground}; border:1px solid {border};"
            "border-radius:12px; padding:7px 12px; font-weight:700;"
            "}"
        )

    @staticmethod
    def _history_status_text(status: str) -> str:
        return {
            "SUCCESS": "Başarılı",
            "PARTIAL": "Kısmi",
            "FAILED": "Hatalı",
            "INTERRUPTED": "Yarım kaldı",
            "RUNNING": "Çalışıyor",
        }.get(status, status)

    @staticmethod
    def _publication_status_text(status: str | None) -> str:
        return {
            "COMMITTED": "Tamamlandı",
            "PUBLISHED": "Yayımlandı · tamamlanma bekliyor",
            "RECOVERY_CONFIRMED": "Yeniden işleme onaylandı",
            None: "Kayıt yok",
        }.get(status, status or "Kayıt yok")

    @staticmethod
    def _review_phase_text(phase: str) -> str:
        return {
            "OPEN": "Açık",
            "ASSIGNED": "Atandı",
            "IN_REVIEW": "İnceleniyor",
            "PENDING_APPROVAL": "Onay bekliyor",
            "APPROVED": "Onaylandı",
            "REJECTED": "Düzeltme bekliyor",
            "CANCELLED": "İptal",
        }.get(phase, phase)

    @staticmethod
    def _output_presence_text(state: str) -> str:
        return {
            "PRESENT": "Dosyalar mevcut",
            "PARTIALLY_MISSING": "Bazı dosyalar bulunamıyor",
            "MISSING": "Kayıtlı dosyalar bulunamıyor",
            "NONE_RECORDED": "Kayıtlı çıktı yok",
        }.get(state, state)

    @staticmethod
    def _processed_source_text(state: str) -> str:
        return {
            "ALL_PROCESSED": "Tam",
            "PARTIALLY_PROCESSED": "Kısmi",
            "NONE_PROCESSED": "İşlenmiş kaydı yok",
            "UNKNOWN": "Bilinmiyor",
            "NO_SOURCES": "Bağlı kaynak yok",
        }.get(state, state)

    def _render_erp_quality_summary(self, records) -> None:
        last_week = filter_operation_records(records, period_days=7)
        trends = build_operation_trend_summary(last_week)
        self.erp_quality_summary.setText(
            " • ".join((
                self._quality_system_text("Netsis", trends.netsis_accepted, trends.netsis_rejected, trends.netsis_rejection_reasons),
                self._quality_system_text("Psoft", trends.psoft_accepted, trends.psoft_rejected, trends.psoft_rejection_reasons),
            ))
        )

    @staticmethod
    def _quality_system_text(system: str, accepted: int, rejected: int, reasons: tuple[tuple[str, int], ...]) -> str:
        base = f"{system}: {accepted} kabul · {rejected} ret"
        if not reasons:
            return base
        top_reasons = ", ".join(
            f"{ERP_REJECTION_REASON_LABELS.get(code, code)} ({count})"
            for code, count in reasons[:2]
        )
        return f"{base} · sık nedenler: {top_reasons}"

    def _populate_completed_manim_results(self) -> None:
        previous_id = self.operation_result_combo.currentData()
        self.operation_result_combo.blockSignals(True)
        self.operation_result_combo.clear()
        for record in self._completed_manim_records:
            acceptance = self._external_acceptance(record)
            erp_text = {
                "ACCEPTED": "Netsis kabul",
                "REJECTED": "Netsis ret",
                "PARTIAL": (
                    f"Netsis sonucu {acceptance.get('recorded_count', 0)}/"
                    f"{acceptance.get('candidate_count', 0)} dosyada"
                ),
            }.get(acceptance.get("verdict", ""), "Netsis sonucu bekleniyor")
            self.operation_result_combo.addItem(
                f"#{record.id} · {self._display_date(record.started_at)} · {erp_text}",
                record.id,
            )
        selected = self.operation_result_combo.findData(previous_id)
        self.operation_result_combo.setCurrentIndex(selected if selected >= 0 else 0)
        self.operation_result_combo.blockSignals(False)
        self._render_completed_manim_result()

    def _selected_completed_manim_record(self):
        operation_id = self.operation_result_combo.currentData()
        return next(
            (record for record in self._completed_manim_records if record.id == operation_id),
            None,
        )

    def _render_completed_manim_result(self) -> None:
        record = self._selected_completed_manim_record()
        if record is None:
            self.operation_result_dashboard.set_summary(None, preview=False)
            self.operation_result_context.setText("Henüz tamamlanmış bir MANİM işlemi yok.")
            self.open_operation_result_button.setEnabled(False)
            self.record_operation_result_button.setEnabled(False)
            return
        summary = simulation_summary_from_payload(
            record.summary.get("operation_result") if isinstance(record.summary, dict) else None
        )
        if summary is not None:
            summary = attach_simulation_details(
                summary,
                [
                    {
                        "decision": movement.decision,
                        "outcome": movement.outcome,
                        "region": movement.region,
                        "bank": movement.bank,
                        "amount": movement.amount,
                        "rule_code": movement.rule_code,
                        "source_file": movement.source_file,
                        "source_row": movement.source_row,
                    }
                    for movement in self.history.financial_movements(record.id)
                ],
            )
        self.operation_result_dashboard.set_summary(summary, preview=False)
        acceptance = self._external_acceptance(record)
        acceptance_text = {
            "ACCEPTED": "Netsis kabul edildi",
            "REJECTED": "Netsis reddetti",
            "PARTIAL": (
                f"Netsis sonucu {acceptance.get('recorded_count', 0)}/"
                f"{acceptance.get('candidate_count', 0)} dosyada kaydedildi"
            ),
        }.get(acceptance.get("verdict", ""), "Netsis sonucu henüz kaydedilmedi")
        if acceptance.get("output_name"):
            acceptance_text += f" · {acceptance['output_name']}"
        if summary is None:
            detail = "Bu eski işlemde kalıcı bölge/banka sonuç özeti bulunmuyor."
        else:
            detail = (
                f"{len(summary.buckets)} bölge/banka · "
                f"{sum(bucket.record_count for bucket in summary.buckets):,} kaynak hareketi"
            )
        self.operation_result_context.setText(
            f"İşlem #{record.id} · {acceptance_text} · {len(record.output_files)} çıktı dosyası. {detail}"
        )
        self.open_operation_result_button.setEnabled(
            any(Path(value).parent.is_dir() for value in record.output_files)
        )
        self.record_operation_result_button.setEnabled(
            bool(record.output_files)
            and bool(self.session and self.session.can("operations.acceptance.record"))
        )

    def _open_completed_manim_output(self) -> None:
        record = self._selected_completed_manim_record()
        if record:
            directory = next(
                (
                    Path(value).parent
                    for value in record.output_files
                    if Path(value).parent.is_dir()
                ),
                None,
            )
            if directory is not None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def _record_completed_manim_acceptance(self) -> None:
        record = self._selected_completed_manim_record()
        if record is None or not self.session or not self.session.can("operations.acceptance.record"):
            return
        output_file = self._select_netsis_output(record)
        if not output_file:
            return
        prompt = QMessageBox(self)
        prompt.setWindowTitle("Netsis aktarım sonucu")
        prompt.setIcon(QMessageBox.Question)
        prompt.setText(f"İşlem #{record.id} için Netsis aktarımı kabul edildi mi?")
        prompt.setInformativeText(
            "Bu seçim yalnız yerel işlem geçmişine denetim sonucu yazar; Excel dosyası ve Netsis aktarımı değişmez."
        )
        prompt.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        prompt.button(QMessageBox.Yes).setText("Kabul edildi")
        prompt.button(QMessageBox.No).setText("Reddedildi")
        prompt.button(QMessageBox.Cancel).setText("Vazgeç")
        choice = prompt.exec()
        if choice == QMessageBox.Cancel:
            return
        verdict = "ACCEPTED" if choice == QMessageBox.Yes else "REJECTED"
        reason_code = ""
        if verdict == "REJECTED":
            labels = [label for _code, label in ERP_REJECTION_REASONS]
            selected, accepted = QInputDialog.getItem(
                self,
                "Netsis ret nedeni",
                "Netsis aktarım ekranında görünen ana hata nedeni:",
                labels,
                0,
                False,
            )
            if not accepted:
                return
            reason_code = next(
                code
                for code, label in ERP_REJECTION_REASONS
                if label == selected
            )
        self._save_completed_manim_acceptance(
            record.id,
            verdict,
            reason_code,
            output_file=output_file,
        )

    def _select_netsis_output(self, record) -> str | None:
        candidates = erp_output_candidates(
            record.module_id,
            "NETSIS",
            record.output_files,
        )
        if not candidates:
            QMessageBox.warning(
                self,
                "Netsis çıktısı bulunamadı",
                "Bu işlemde Netsis'e aktarılabilecek bir havale veya virman dosyası yok.",
            )
            return None
        if len(candidates) == 1:
            return candidates[0]
        choices = output_choice_labels(candidates)
        selected, accepted = QInputDialog.getItem(
            self,
            "Netsis çıktısı",
            "Sonucunu kaydedeceğiniz dosyayı seçin:",
            list(choices),
            0,
            False,
        )
        return choices.get(selected) if accepted else None

    def _save_completed_manim_acceptance(
        self,
        operation_id: int,
        verdict: str,
        reason_code: str = "",
        *,
        output_file: str | Path | None = None,
    ) -> bool:
        """Write only an explicit user ERP result, never an automatic approval."""
        if not self.session or not self.session.can("operations.acceptance.record"):
            return False
        try:
            self.history.record_external_acceptance(
                operation_id,
                system="NETSIS",
                verdict=verdict,
                reason_code=reason_code,
                output_file=output_file,
            )
        except Exception as error:
            QMessageBox.warning(self, "Netsis sonucu kaydedilemedi", str(error))
            return False
        self.refresh()
        QMessageBox.information(
            self,
            "Netsis sonucu kaydedildi",
            "Netsis kabul sonucu işlem geçmişine eklendi."
            if verdict == "ACCEPTED"
            else "Netsis ret sonucu işlem geçmişine eklendi.",
        )
        return True

    @staticmethod
    def _external_acceptance(record) -> dict[str, object]:
        value = aggregate_erp_acceptance(
            record.module_id,
            "NETSIS",
            record.output_files,
            record.summary,
        )
        return {
            "system": value.system,
            "verdict": value.status,
            "reason_code": value.reason_code,
            "output_name": value.output_name,
            "candidate_count": value.candidate_count,
            "recorded_count": value.recorded_count,
        }

    def _selected_rejected_manim_record(self):
        row = self.rejection_table.currentRow()
        if row < 0 or row >= len(self._rejected_manim_records):
            return None
        return self._rejected_manim_records[row]

    def _render_rejected_manim_records(self) -> None:
        records = list(self._rejected_manim_records)
        self.rejection_table.setRowCount(len(records))
        for row, record in enumerate(records):
            outputs = [Path(value) for value in record.output_files]
            sources = [Path(value) for value in record.input_files]
            existing = sum(path.is_file() for path in sources)
            accepted_output_name = self._external_acceptance(record).get("output_name", "")
            output_text = accepted_output_name or (
                outputs[0].name if len(outputs) == 1
                else f"{outputs[0].name} + {len(outputs) - 1} dosya"
                if outputs else "Çıktı kaydı yok"
            )
            reason_code = self._external_acceptance(record).get("reason_code", "")
            reason = ERP_REJECTION_REASON_LABELS.get(reason_code, "Neden belirtilmedi")
            source_status = (
                f"Hazır · {existing}/{len(sources)}"
                if sources and existing == len(sources)
                else f"Eksik · {existing}/{len(sources)}"
            )
            values = (
                self._display_date(record.started_at),
                f"#{record.id}",
                output_text,
                reason,
                source_status,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 4):
                    item.setTextAlignment(Qt.AlignCenter)
                if column == 2:
                    item.setToolTip("\n".join(str(path) for path in outputs))
                self.rejection_table.setItem(row, column, item)
        if records:
            self.rejection_table.selectRow(0)
        else:
            self._update_rejection_actions()

    def _update_rejection_actions(self) -> None:
        record = self._selected_rejected_manim_record()
        sources = [Path(value) for value in record.input_files] if record else []
        existing = [path for path in sources if path.is_file()]
        can_retry = bool(
            record
            and sources
            and len(existing) == len(sources)
            and self.session
            and self.session.allows_module("manim_transfer")
        )
        self.prepare_manim_retry_button.setEnabled(can_retry)
        output_directories = (
            [Path(value).parent for value in record.output_files] if record else []
        )
        self.open_rejected_output_button.setEnabled(
            any(directory.is_dir() for directory in output_directories)
        )
        if record is None:
            self.rejection_detail.setText("Kayıtlı bir Netsis ret sonucu bulunmuyor.")
            return
        if not sources:
            self.rejection_detail.setText(
                "Bu eski işlemde kaynak dosya bilgisi bulunmadığı için yeniden çalışma hazırlanamaz."
            )
            return
        missing = [path.name for path in sources if not path.is_file()]
        if missing:
            self.rejection_detail.setText(
                "Yeniden çalışma için kaynak dosyalar eksik: " + ", ".join(missing)
            )
        else:
            self.rejection_detail.setText(
                f"{len(sources)} kaynak dosya hazır. Seçilen çıktı biçimiyle MANİM çalışma alanına geçebilirsiniz."
            )

    def _open_rejected_output(self) -> None:
        record = self._selected_rejected_manim_record()
        if record:
            directory = next(
                (
                    Path(value).parent
                    for value in record.output_files
                    if Path(value).parent.is_dir()
                ),
                None,
            )
            if directory is not None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def _prepare_manim_retry(self) -> None:
        record = self._selected_rejected_manim_record()
        if record is None or not self.session or not self.session.allows_module("manim_transfer"):
            return
        sources = [Path(value) for value in record.input_files]
        missing = [path for path in sources if not path.is_file()]
        if not sources or missing:
            self._update_rejection_actions()
            return
        self.safe_manim_retry_requested.emit(
            {
                "operation_id": record.id,
                "input_files": [str(path) for path in sources],
                "output_profile_id": str(self.retry_profile_combo.currentData()),
                "reason": operation_attention_text(record),
            }
        )

    def _selected_publication(self):
        row = self.recovery_table.currentRow()
        if row < 0 or row >= len(self._pending_publications):
            return None
        return self._pending_publications[row]

    def _update_recovery_actions(self) -> None:
        publication = self._selected_publication() if hasattr(self, "recovery_table") else None
        self.open_recovery_output_button.setEnabled(publication is not None)
        self.approve_retry_button.setEnabled(publication is not None and bool(self.session and self.session.can("operations.review.reopen")))

    def _render_pending_publications(self) -> None:
        publications = list(self._pending_publications)
        self.recovery_table.setRowCount(len(publications))
        for row, publication in enumerate(publications):
            values = (
                self._display_date(publication.published_at),
                str(len(publication.source_hashes)),
                publication.output_dir,
                "Kurtarma gerekli",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column in (1, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self.recovery_table.setItem(row, column, item)

    def _open_recovery_output(self) -> None:
        publication = self._selected_publication()
        if publication is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(publication.output_dir))

    def _approve_recovery_retry(self) -> None:
        if not self.identity_store or not self.session:
            return
        if not self.identity_store.current_session(self.session).can("operations.review.reopen"):
            return
        publication = self._selected_publication()
        if publication is None:
            return
        answer = QMessageBox.warning(
            self,
            "Yeniden işlem onayı",
            "Bu işlem, eski çıktı klasörünü silmez. Yalnız seçili kaynakların yeniden "
            "işlenmesine izin verir. Eski çıktının Netsis/Psoft'a aktarılmadığını kontrol ettiniz mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            self.publication_journal.approve_retry(publication.publication_id)
        except Exception as error:
            QMessageBox.warning(self, "Yayın ve kurtarma", str(error))
            return
        self.refresh()

    def _render_attention_records(self) -> None:
        status = self.status_filter.currentData() if hasattr(self, "status_filter") else ""
        needle = self.search_input.text().strip().casefold() if hasattr(self, "search_input") else ""
        records = [
            record for record in self._attention_records
            if (not status or record.status == status)
            and (not needle or needle in " ".join((record.module_name, record.actor, operation_attention_text(record))).casefold())
        ]
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = (
                self._display_date(record.started_at),
                record.module_name,
                self._status_text(record.status),
                operation_attention_text(record),
                record.actor or "-",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row, column, item)

    @staticmethod
    def _display_date(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return value

    @staticmethod
    def _status_text(status: str) -> str:
        return {
            "PARTIAL": "Kısmi",
            "FAILED": "Hatalı",
            "INTERRUPTED": "Yarım kaldı",
        }.get(status, status)

    @staticmethod
    def _queue_status_text(status: str) -> str:
        return {"OPEN": "Açık", "ASSIGNED": "Atandı", "RESOLVED": "Çözüldü", "CANCELLED": "İptal"}.get(status, status)
