"""Premium accounting-automation workspace backed only by existing read models.

The visual composition deliberately mirrors the approved Çarpan mockup while
keeping every number bound to parser/engine facts.  It introduces no write or
routing semantics; actions are emitted back to the existing MANİM workflow.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QFontMetricsF, QPainter, QPen, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.ui.accounting_view import (
    AccountingView,
    detail_rows,
    load_sources,
    money_text,
    previous_operation,
    reconcile,
)
from app.ui.background_task import BackgroundWorker
from app.ui.workspace_icons import workspace_icon
from app.ui.operation_breakdown import CATEGORIES, bank_breakdown, regional_breakdown
from app.ui.accounting_outputs_page import output_table


# ---------------------------------------------------------------------------
# Small visual building blocks.  They are local to the accounting workspace so
# the rest of the application can continue using the shared Phase-1 system.
# ---------------------------------------------------------------------------


def _table(headers: list[str], object_name: str = "attentionTable") -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setObjectName(object_name)
    widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SingleSelection)
    widget.setAlternatingRowColors(False)
    widget.setWordWrap(False)
    widget.verticalHeader().hide()
    widget.verticalHeader().setDefaultSectionSize(34)
    widget.horizontalHeader().setHighlightSections(False)
    widget.horizontalHeader().setSectionsClickable(True)
    widget.setShowGrid(True)
    widget.setTextElideMode(Qt.ElideRight)
    palette = widget.palette()
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        for role, color in ((QPalette.Text, "#203654"), (QPalette.Base, "#FFFFFF"),
                            (QPalette.HighlightedText, "#173A79"), (QPalette.Highlight, "#E8EFFF")):
            palette.setColor(group, role, QColor(color))
    widget.setPalette(palette)
    return widget


def _amount_text(value) -> str:
    """Mockup-style amount formatting without changing public money_text API."""
    text = money_text(value)
    return "—" if text == "—" else text.removesuffix(" TL") + " ₺"


_TURKISH_MONTHS = (
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)


def _operation_day_text(rows) -> str | None:
    """Return the single source operation day in mockup-friendly Turkish text."""
    parsed = set()
    for row in rows:
        raw = str(getattr(row, "date", "") or "").strip()
        if not raw:
            continue
        value = None
        for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                value = datetime.strptime(raw[:10], pattern).date()
                break
            except ValueError:
                continue
        if value is not None:
            parsed.add(value)
    if len(parsed) != 1:
        return None
    value = next(iter(parsed))
    return f"{value.day} {_TURKISH_MONTHS[value.month]} {value.year}"


def _display_datetime(raw: object) -> str:
    """Render known source timestamps in the compact Turkish workspace format."""
    text = str(raw or "").strip()
    if not text:
        return "—"
    candidate = text.replace("Z", "+00:00")
    try:
        value = datetime.fromisoformat(candidate)
        return value.strftime("%d.%m.%Y %H:%M") if value.time().isoformat() != "00:00:00" else value.strftime("%d.%m.%Y")
    except ValueError:
        pass
    for pattern in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            value = datetime.strptime(text[:19], pattern)
            return value.strftime("%d.%m.%Y %H:%M") if "%H" in pattern else value.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return text


def _display_bank_name(value: object) -> str:
    key = str(value or "").strip().upper()
    return {
        "GARANTI": "Garanti",
        "GARANTI BBVA": "Garanti",
        "YKB": "Yapı Kredi",
        "YAPI KREDI": "Yapı Kredi",
        "YAPIKREDI": "Yapı Kredi",
        "ZIRAAT": "Ziraat",
        "ZIRAAT BANKASI": "Ziraat",
        "AKBANK": "Akbank",
        "BILINMEYEN_BANKA": "Bilinmeyen banka",
    }.get(key, str(value or "—").replace("_", " ").title())

_BANK_BRANDS = {
    "GARANTI": {"label": "Garanti", "family": "garanti", "accent": "#008E62"},
    "GARANTI BBVA": {"label": "Garanti", "family": "garanti", "accent": "#008E62"},
    "YKB": {"label": "Yapı Kredi", "family": "yapikredi", "accent": "#0055A6"},
    "YAPI KREDI": {"label": "Yapı Kredi", "family": "yapikredi", "accent": "#0055A6"},
    "YAPIKREDI": {"label": "Yapı Kredi", "family": "yapikredi", "accent": "#0055A6"},
    "ZIRAAT": {"label": "Ziraat", "family": "ziraat", "accent": "#E3232C"},
    "ZIRAAT BANKASI": {"label": "Ziraat", "family": "ziraat", "accent": "#E3232C"},
    "AKBANK": {"label": "Akbank", "family": "akbank", "accent": "#D71920"},
    "BILINMEYEN_BANKA": {"label": "Bilinmeyen banka", "family": "unknown", "accent": "#667085"},
}

_ENGINE_LABELS = {
    "AUTOMATIC_CUSTOMER_MATCH": "Otomatik müşteri eşleşmesi",
    "MANUAL_CUSTOMER_MATCH": "Manuel müşteri eşleşmesi",
    "CUSTOMER_MATCH_REVIEW": "Müşteri eşleşmesi kontrolü",
    "MANIM_KOD": "MANİM cari kod eşleşmesi",
    "ACIKLAMA_KODU": "Açıklamadaki cari kod eşleşmesi",
    "MANUEL_ESLESTIRME": "Manuel eşleştirme",
    "MISSING_BANK_ACCOUNT_CODE": "Banka hesap kodu eksik",
    "COMBINED_BANK_MOVEMENTS_EXACT": "Birleşik banka hareketi eşleşti",
    "COMBINED_BANK_MOVEMENTS_DIFFERENCE": "Birleşik banka hareketinde fark var",
    "MANUAL_COMBINED_MATCH": "Manuel birleşik hareket eşleşmesi",
    "MANUAL_PARTIAL_MATCH": "Kısmi manuel eşleşme",
    "MANUAL_ROUTE": "Manuel yönlendirme",
}


def _display_engine_code(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "—"
    if raw in _ENGINE_LABELS:
        return _ENGINE_LABELS[raw]
    # Only prettify machine-style identifiers. Human-written Turkish reasons
    # must pass through verbatim.
    if raw.replace("_", "").isalnum() and raw == raw.upper() and "_" in raw:
        words = raw.replace("_", " ").lower()
        return words[:1].upper() + words[1:]
    return raw


def _bank_brand(value: object) -> dict[str, str]:
    raw = str(value or "").strip()
    key = raw.upper()
    brand = dict(_BANK_BRANDS.get(key, {
        "label": raw.replace("_", " ").title() or "—",
        "family": "unknown",
        "accent": "#4A6282",
    }))
    brand["key"] = key or "UNKNOWN"
    return brand


class _BankLogo(QLabel):
    """Render a crisp bundled symbol-only bank logo in compact tables."""

    _FILES = {
        "garanti": "garanti_symbol.png",
        "yapikredi": "yapikredi_symbol.png",
        "ziraat": "ziraat_symbol.png",
    }
    _CROP = {
        # Transparent bounds of the bundled 96x96 symbol assets.  Cropping
        # before scaling keeps narrow marks such as Ziraat fully visible.
        "garanti": (16, 9, 63, 78),
        "yapikredi": (7, 26, 82, 43),
        "ziraat": (36, 25, 23, 46),
    }

    def __init__(self, family: str, label: str, asset_root: Path | None = None, parent=None):
        super().__init__(parent)
        self.family = family
        self.setObjectName("automationBankMark")
        self.setAccessibleName(f"{label} logosu")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(18, 18)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setToolTip(label)

        filename = self._FILES.get(family)
        roots = []
        if asset_root is not None:
            roots.append(Path(asset_root))
        roots.append(Path(__file__).resolve().parents[2])
        for root in roots:
            candidate = root / "assets" / "bank_logos" / str(filename or "")
            if filename and candidate.exists():
                pixmap = QPixmap(str(candidate))
                if not pixmap.isNull():
                    x, y, w, h = self._CROP.get(family, (0, 0, pixmap.width(), pixmap.height()))
                    mark = pixmap.copy(x, y, w, h)
                    self.setPixmap(mark.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return

        # Missing assets must stay obvious during QA instead of silently
        # looking like an empty bank column.
        self.setText("?")
        self.setStyleSheet("color:#60738D; font-size:12px; font-weight:700; background:transparent;")


def _bank_cell(value: object, asset_root: Path | None = None) -> QWidget:
    brand = _bank_brand(value)
    host = QWidget()
    host.setObjectName("automationBankCell")
    host.setToolTip(brand["label"])
    host.setAutoFillBackground(True)
    palette = host.palette()
    palette.setColor(QPalette.Window, QColor("#FFFFFF"))
    host.setPalette(palette)
    row = QHBoxLayout(host)
    row.setContentsMargins(2, 0, 2, 0)
    row.setSpacing(4)
    mark = _BankLogo(brand["family"], brand["label"], asset_root, host)
    mark.setProperty("bankKey", brand["key"])
    name = _label(brand["label"], "automationBankName")
    name.setToolTip(brand["label"])
    row.addWidget(mark, 0, Qt.AlignVCenter)
    row.addWidget(name, 0, Qt.AlignVCenter)
    row.addStretch(1)
    return host



def _label(text: str, object_name: str, *, wrap: bool = False) -> QLabel:
    item = QLabel(text)
    item.setObjectName(object_name)
    item.setWordWrap(wrap)
    return item


class _StatBlock(QFrame):
    def __init__(self, icon: str, title: str, detail: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("automationStatBlock")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(7)
        self.icon = _label(icon, "automationStatIcon")
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setFixedWidth(22)
        symbol = {"▱": "files", "⌖": "region", "▤": "record"}.get(icon)
        if symbol:
            self.icon.setPixmap(workspace_icon(symbol, 22).pixmap(22, 22))
        text = QVBoxLayout()
        text.setSpacing(1)
        self.value = _label(title, "automationStatValue")
        self.detail = _label(detail, "automationStatDetail")
        self.detail.setWordWrap(True)
        self.value.setWordWrap(True)
        text.addWidget(self.value)
        text.addWidget(self.detail)
        layout.addWidget(self.icon)
        layout.addLayout(text, 1)

    def set_value(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.value.setToolTip(value)
        self.detail.setText(detail)
        self.detail.setToolTip(detail)


class _Step(QFrame):
    def __init__(self, number: int, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("automationStep")
        self._state = "pending"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.number = QLabel(str(number))
        self.number.setObjectName("automationStepNumber")
        self.number.setAlignment(Qt.AlignCenter)
        self.number.setFixedSize(20, 20)
        self.title = QLabel(title)
        self.title.setObjectName("automationStepTitle")
        layout.addWidget(self.number)
        layout.addWidget(self.title)
        self.connector = _label("—", "workflowConnector")
        layout.addWidget(self.connector)
        self.connector.setVisible(number < 6)
        self.set_state("pending")

    def set_state(self, state: str) -> None:
        self._state = state
        self.setProperty("stepState", state)
        self.number.setProperty("stepState", state)
        self.title.setProperty("stepState", state)
        if state == "complete":
            self.number.setText("✓")
        else:
            self.number.setText(str(self.property("stepNumber") or ""))
        for widget in (self, self.number, self.title):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def set_number(self, number: int) -> None:
        self.setProperty("stepNumber", number)
        if self._state != "complete":
            self.number.setText(str(number))


class _DecisionLegend(QFrame):
    def __init__(self, tone: str, parent=None):
        super().__init__(parent)
        self.setObjectName("decisionLegend")
        self.setProperty("tone", tone)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        dot = QLabel("●")
        dot.setObjectName("decisionDot")
        dot.setProperty("tone", tone)
        self.text = QLabel()
        self.text.setObjectName("decisionLegendText")
        row.addWidget(dot)
        row.addWidget(self.text)


class _SegmentBar(QFrame):
    """Simple deterministic segment bar; stretches represent record counts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("decisionBar")
        self.row = QHBoxLayout(self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(1)
        self._segments: list[QFrame] = []
        for tone in ("success", "warning", "manual", "critical"):
            frame = QFrame()
            frame.setObjectName("decisionBarSegment")
            frame.setProperty("tone", tone)
            frame.setMinimumWidth(0)
            self._segments.append(frame)
            self.row.addWidget(frame, 1)

    def set_counts(self, counts: tuple[int, int, int, int]) -> None:
        total = sum(counts)
        self.setProperty("empty", "true" if total <= 0 else "false")
        for index, (frame, count) in enumerate(zip(self._segments, counts)):
            self.row.setStretch(index, max(0, count))
            # With no decisions yet the mockup keeps a neutral track; never
            # paint a synthetic green "success" segment for an empty state.
            frame.setVisible(total > 0 and count > 0)
        self.style().unpolish(self)
        self.style().polish(self)


class _PremiumComboBox(QComboBox):
    """Flat combo with a stable chevron instead of the native Windows arrow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chevron = QLabel("⌄", self)
        self._chevron.setObjectName("automationComboArrow")
        self._chevron.setAlignment(Qt.AlignCenter)
        self._chevron.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._chevron.setFixedWidth(20)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._chevron.setGeometry(self.width() - 25, 0, 20, self.height())
        self._chevron.raise_()




class _FinanceMetricBadge(QLabel):
    """Exact mockup KPI badge using a high-DPI static asset; no custom painting."""

    _FILES = {
        "success": "kpi_success_exact4x.png",
        "outflow": "kpi_outflow_exact4x.png",
        "info": "kpi_info_exact4x.png",
    }

    def __init__(self, tone: str, parent=None):
        super().__init__(parent)
        self.setObjectName("automationMetricIcon")
        self.setProperty("tone", tone)
        self.setProperty("variant", "finance")
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setFixedSize(38, 38)
        asset = Path(__file__).resolve().parents[2] / "assets" / "kpi_mockup_native" / self._FILES[tone]
        pixmap = QPixmap(str(asset))
        if pixmap.isNull():
            raise RuntimeError(f"Exact KPI mockup asset missing: {asset}")
        pixmap.setDevicePixelRatio(4.0)
        self.setPixmap(pixmap)

class _FitCurrencyLabel(QLabel):
    """Scale one financial value to its available width without ellipsis."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("automationMetricValue")
        self.setProperty("variant", "finance")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._fitting = False
        self._fit_font()

    def setText(self, text: str) -> None:
        super().setText(text)
        self._fit_font()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_font()

    def _fit_font(self) -> None:
        if self._fitting or not self.text():
            return
        self._fitting = True
        try:
            dense = self.property("dense") == "true"
            preferred = 16 if dense else 18
            available = max(1, self.contentsRect().width())
            selected = 9
            for size in range(preferred, 8, -1):
                self.setStyleSheet(f"font-size:{size}px;")
                if QFontMetricsF(self.font()).horizontalAdvance(self.text()) <= available:
                    selected = size
                    break
            self.setStyleSheet(f"font-size:{selected}px;")
            self.setToolTip(self.text())
        finally:
            self._fitting = False


class _MetricTile(QFrame):
    """Premium compact KPI card with a strong semantic icon and type hierarchy."""

    def __init__(self, icon: str, label: str, tone: str = "neutral", parent=None):
        super().__init__(parent)
        self.setObjectName("automationMetricTile")
        self.setProperty("tone", tone)
        finance_metric = label in {"Toplam giren", "Toplam çıkan", "Net hareket"}
        net_metric = label == "Net hareket"
        self.setProperty("variant", "finance" if finance_metric else "status")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6 if net_metric else (12 if finance_metric else 7), 8 if finance_metric else 6,
                                  6 if net_metric else (12 if finance_metric else 7), 8 if finance_metric else 6)
        layout.setSpacing(3)

        body = QHBoxLayout()
        body.setSpacing(5 if net_metric else (9 if finance_metric else 7))
        if finance_metric:
            self.icon = _FinanceMetricBadge(tone, self)
        else:
            self.icon = _label(icon, "automationMetricIcon")
            self.icon.setProperty("tone", tone)
            self.icon.setProperty("variant", "status")
            self.icon.setAlignment(Qt.AlignCenter)
            self.icon.setFixedSize(24, 24)
        body.addWidget(self.icon, 0, Qt.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(0)
        self.label = _label(label, "automationMetricLabel")
        self.label.setToolTip(label)
        self.value = _FitCurrencyLabel("—", self) if net_metric else _label("—", "automationMetricValue")
        self.detail = _label("Henüz hesaplanmadı", "automationMetricDetail")
        for text_widget in (self.label, self.value, self.detail):
            text_widget.setProperty("variant", "finance" if finance_metric else "status")
        # Typography may grow during parity passes, but a text size hint must
        # never force the seven-card dashboard wider than its viewport.
        for text_widget in (self.label, self.value, self.detail):
            text_widget.setMinimumWidth(0)
            text_widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        if net_metric:
            # Keep the badge in its own column. All three text rows share the
            # adjacent text column so a long amount can never slide beneath
            # the badge or collide with it.
            body.setAlignment(self.icon, Qt.AlignTop)
            text.addWidget(self.label)
            text.addWidget(self.value)
            text.addWidget(self.detail)
            body.addLayout(text, 1)
            layout.addLayout(body)
        else:
            text.addWidget(self.label)
            text.addWidget(self.value)
            text.addWidget(self.detail)
            body.addLayout(text, 1)
            layout.addLayout(body)

        self.progress = QProgressBar(self)
        self.progress.setObjectName("metricProgress")
        self.progress.setProperty("tone", tone)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setVisible(tone in {"success", "warning", "manual", "critical"} and label not in {"Toplam giren", "Toplam çıkan"})
        layout.addWidget(self.progress)

    def set_value(self, value: str, detail: str = "") -> None:
        self.value.setText(value)
        self.value.setToolTip(value)
        self.detail.setText(detail)
        self.detail.setToolTip(detail)


class _ReconCell(QFrame):
    def __init__(self, label: str, *, tone: str = "neutral", parent=None):
        super().__init__(parent)
        self.setObjectName("automationReconCell")
        self.setProperty("tone", tone)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(2)
        self.label = _label(label, "automationReconLabel")
        self.value = _label("—", "automationReconValue")
        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, value: str) -> None:
        self.value.setText(value)


class AccountingWorkspace(QWidget):
    """The approved Muhasebe Otomasyon Merkezi workspace.

    It stays read-only with respect to accounting decisions.  All mutating
    actions are emitted to the existing module and ProcessingEngine flow.
    """

    sources_ready = Signal()
    add_sources_requested = Signal()
    source_tools_requested = Signal()
    clear_sources_requested = Signal()
    preview_requested = Signal()
    output_requested = Signal()
    matching_requested = Signal()
    outputs_requested = Signal()

    def __init__(self, history, paths, parent=None):
        super().__init__(parent)
        self.setObjectName("accountingWorkspace")
        self.history, self.paths = history, paths
        self.view = AccountingView()
        self.summary = None
        self.audits = ()
        self.operation_reader = None
        self._thread = None
        self._pending = ()
        self._active = ()
        self._operation_id = None
        self._preview = False
        self._output_done = False
        self._last_output_dir: Path | None = None
        self._last_created_files: tuple[Path, ...] = ()
        self._unresolved_count = 0
        self._busy = False
        self._rows = ()
        self._mode = "new"
        self._build_ui()
        self.render()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Kept for compatibility with the Phase-2 tests/read-model surface.
        self.facts = QLabel(self)
        self.facts.hide()
        self.financial = QLabel(self)
        self.financial.hide()
        self.status_summary = QLabel(self)
        self.status_summary.hide()

        self.stack = QStackedWidget()
        self.stack.setObjectName("accountingStack")
        self.new_page = self._build_new_work_page()
        self.sources_page = self._build_sources_page()
        self.stack.addWidget(self.new_page)
        self.stack.addWidget(self.sources_page)
        root.addWidget(self.stack, 1)

    def _build_new_work_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("automationNewWorkPage")

        # The approved mockup is a two-column work surface: the operational
        # canvas occupies the left side, while record context is always present
        # as a full-height inspector on the right.
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        shell = QHBoxLayout()
        page_layout.addLayout(shell, 1)
        shell.setContentsMargins(10, 0, 10, 0)
        shell.setSpacing(8)

        canvas = QWidget()
        canvas.setObjectName("automationCanvas")
        canvas.setMinimumWidth(0)
        canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        root = QVBoxLayout(canvas)
        root.setContentsMargins(0, 0, 0, 3)
        root.setSpacing(3)

        # Page header.
        header = QHBoxLayout()
        header.setSpacing(9)
        title_icon = QLabel("▣")
        title_icon.setObjectName("automationTitleIcon")
        title_icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        title_icon.setFixedWidth(27)
        title_icon.setPixmap(workspace_icon("workflow", 24, "#315BE8").pixmap(24, 24))
        header.addWidget(title_icon)
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        self.page_title = _label("Muhasebe Otomasyon Merkezi", "automationPageTitle")
        self.page_title.setWordWrap(True)
        self.page_subtitle = _label("Yeni çalışma · Kaynakları ekleyerek başlayın", "automationPageSubtitle")
        header_text.addWidget(self.page_title)
        header_text.addWidget(self.page_subtitle)
        header.addLayout(header_text, 1)
        self.output_access = QFrame()
        self.output_access.setObjectName("automationOutputAccess")
        output_access_layout = QHBoxLayout(self.output_access)
        output_access_layout.setContentsMargins(8, 3, 4, 3)
        output_access_layout.setSpacing(6)
        self.output_access_label = _label("Çıktı hazır", "automationOutputAccessLabel")
        output_access_layout.addWidget(self.output_access_label)
        self.open_output_button = QPushButton("Çıktı klasörünü aç")
        self.open_output_button.setObjectName("automationOutputOpen")
        self.open_output_button.clicked.connect(self.open_output_location)
        output_access_layout.addWidget(self.open_output_button)
        self.output_access.hide()
        self.header_state = _label("Kaynak bekleniyor", "automationHeaderState")
        self.header_state.setProperty("state", "idle")
        self.header_state.setAlignment(Qt.AlignCenter)
        self.header_state.hide()
        self.detail_toggle = QPushButton("Ayrıntı", page)
        self.detail_toggle.setObjectName("secondary")
        self.detail_toggle.setCheckable(True)
        self.detail_toggle.setChecked(True)
        self.detail_toggle.clicked.connect(lambda checked: self.set_inspector_visible(checked))
        header.addWidget(self.detail_toggle, 0, Qt.AlignTop)
        self.detail_toggle.hide()
        header.setContentsMargins(8, 0, 8, 3)
        page_layout.insertLayout(0, header)

        # Source summary rail.  Values remain strictly data-backed; icons are
        # presentation only.
        summary_rail = QFrame()
        summary_rail.setObjectName("automationSummaryRail")
        summary_layout = QGridLayout(summary_rail)
        self.summary_layout = summary_layout
        summary_layout.setContentsMargins(4, 1, 4, 1)
        summary_layout.setSpacing(0)
        self.source_stat = _StatBlock("▱", "0 kaynak dosya", "Excel")
        self.region_stat = _StatBlock("⌖", "0 bölge", "Kaynaklar otomatik sınıflandırılır")
        self.record_stat = _StatBlock("▤", "0 kayıt", "Muhasebe hareketi")
        for index, block in enumerate((self.source_stat, self.region_stat, self.record_stat)):
            summary_layout.addWidget(block, 0, index)
        self.add_source_button = QPushButton("⊕  Dosya ekle")
        self.add_source_button.setObjectName("automationAddSource")
        self.add_source_button.setToolTip(
            "MANİM hareket dosyaları ile hazırlanmış tahsilat raporunu bu çalışmaya ekleyin."
        )
        self.add_source_button.clicked.connect(lambda _checked=False: self.add_sources_requested.emit())
        summary_actions = QHBoxLayout()
        self.summary_actions = summary_actions
        summary_actions.addStretch(1)
        summary_actions.addWidget(self.add_source_button)
        self.source_tools_button = QPushButton("⋯")
        self.source_tools_button.setObjectName("automationAddSource")
        self.source_tools_button.setAccessibleName("Kaynak hazırlama araçlarını aç")
        self.source_tools_button.setToolTip("FOM Rapor Motoru ve müşteri listesi araçlarını aç")
        self.source_tools_button.setFixedWidth(36)
        self.source_tools_button.clicked.connect(
            lambda _checked=False: self.source_tools_requested.emit()
        )
        summary_actions.addWidget(self.source_tools_button)
        self.clear_source_button = QPushButton("Temizle")
        self.clear_source_button.setObjectName("automationClearSource")
        self.clear_source_button.clicked.connect(lambda _checked=False: self.clear_sources_requested.emit())
        self.clear_source_button.hide()
        summary_actions.addWidget(self.clear_source_button)
        summary_layout.addLayout(summary_actions, 0, 3)
        root.addWidget(summary_rail)

        # Workflow rail.
        step_rail = QFrame()
        step_rail.setObjectName("automationStepRail")
        step_layout = QGridLayout(step_rail)
        self.step_layout = step_layout
        step_layout.setContentsMargins(6, 3, 6, 3)
        step_layout.setSpacing(3)
        titles = ("Kaynaklar", "Şema eşleme", "Eşleştirme & kurallar", "İnceleme", "Doğrulama", "Çıktı")
        self.steps: list[_Step] = []
        for index, title in enumerate(titles, 1):
            step = _Step(index, title)
            step.set_number(index)
            self.steps.append(step)
            step_layout.addWidget(step, 0, index - 1)
        self.step_note = _label("Kaynak bekleniyor", "automationStepNote")
        self.step_note.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.step_note.setParent(step_rail)
        self.step_note.hide()
        root.addWidget(step_rail)

        # Approved mockup metric strip: three financial facts followed by four
        # decision-status facts. Empty state keeps structure without fake data.
        metric_strip = QFrame()
        self.metric_strip = metric_strip
        metric_strip.setObjectName("automationMetricStrip")
        metric_layout = QGridLayout(metric_strip)
        self.metric_layout = metric_layout
        metric_layout.setContentsMargins(5, 4, 5, 4)
        metric_layout.setSpacing(4)
        self.metric_incoming = _MetricTile("↓", "Toplam giren", "success")
        self.metric_outgoing = _MetricTile("↑", "Toplam çıkan", "outflow")
        self.metric_net = _MetricTile("▥", "Net hareket", "info")
        self.metric_auto = _MetricTile("✓", "Otomatik işlendi", "success")
        self.metric_review = _MetricTile("!", "Kontrol gereken", "warning")
        self.metric_manual = _MetricTile("!", "Manuel inceleme", "manual")
        self.metric_invalid = _MetricTile("!", "Eksik / geçersiz", "critical")
        self.metric_tiles = (
            self.metric_incoming, self.metric_outgoing, self.metric_net,
            self.metric_auto, self.metric_review, self.metric_manual, self.metric_invalid,
        )
        for index, tile in enumerate(self.metric_tiles):
            metric_layout.addWidget(tile, 0, index)
        # Financial KPI values need more horizontal room than status counts.
        # Keep the accepted seven-card strip while preventing long currency
        # amounts from being clipped at normal desktop widths.
        for column, stretch in enumerate((13, 13, 11, 10, 10, 10, 10)):
            metric_layout.setColumnStretch(column, stretch)
        root.addWidget(metric_strip)

        # Retain the old distribution rail as a hidden compatibility surface.
        # The visible mockup uses the metric cards above.
        decision = QFrame()
        decision.setObjectName("automationDecisionRail")
        decision_layout = QVBoxLayout(decision)
        decision_layout.setContentsMargins(10, 6, 10, 6)
        decision_layout.setSpacing(4)
        legends = QHBoxLayout()
        legends.setSpacing(18)
        self.legend_auto = _DecisionLegend("success")
        self.legend_review = _DecisionLegend("warning")
        self.legend_manual = _DecisionLegend("manual")
        self.legend_error = _DecisionLegend("critical")
        for legend in (self.legend_auto, self.legend_review, self.legend_manual, self.legend_error):
            legends.addWidget(legend)
        legends.addStretch(1)
        self.decision_total = _label("0 kayıt", "decisionTotal")
        legends.addWidget(self.decision_total)
        decision_layout.addLayout(legends)
        self.decision_bar = _SegmentBar()
        decision_layout.addWidget(self.decision_bar)
        decision.setFixedHeight(68)
        # Keep the hidden compatibility rail in the Qt object tree.  V6 kept
        # references to its child labels for legacy tests/rendering but did not
        # insert the parent frame into a layout, so the parent could be
        # garbage-collected after _build_new_work_page() and Shiboken would
        # report "Internal C++ object ... already deleted" during render().
        self.decision_rail = decision
        root.addWidget(self.decision_rail)
        self.decision_rail.hide()

        # Accounting conservation strip.  Unsupported sub-buckets remain "—"
        # rather than manufacturing totals.
        recon_panel = QFrame()
        recon_panel.setObjectName("automationReconciliationStrip")
        recon_layout = QVBoxLayout(recon_panel)
        recon_layout.setContentsMargins(7, 2, 7, 2)
        recon_layout.setSpacing(1)
        recon_title = QHBoxLayout()
        recon_title.setSpacing(6)
        recon_icon = _label("", "automationReconIcon")
        recon_icon.setPixmap(workspace_icon("balance", 18).pixmap(18, 18))
        recon_title.addWidget(recon_icon)
        recon_title.addWidget(_label("Muhasebe mutabakat özeti", "automationReconTitle"))
        recon_title.addStretch(1)
        recon_layout.addLayout(recon_title)
        recon_values = QGridLayout()
        self.recon_layout = recon_values
        recon_values.setSpacing(0)
        self.recon_source = _ReconCell("Kaynak toplamı")
        self.recon_source.setToolTip('Yüklenen MANİM hareketlerinin işaretli net toplamı: giren − çıkan. Brüt gelen toplamı değildir.')
        self.recon_normal = _ReconCell("Normal havale")
        self.recon_branch = _ReconCell("Şubeli")
        self.recon_reference = _ReconCell("Referanslı")
        self.recon_payment = _ReconCell("Ödeme onaylandı")
        self.recon_virman = _ReconCell("Virman")
        self.recon_virman.setToolTip('Virman hareketlerinin giriş/çıkış yönünden bağımsız mutlak hareket hacmi.')
        self.recon_review = _ReconCell("İncelemede")
        self.recon_difference = _ReconCell("Fark", tone="success")
        self.recon_cells = (
            self.recon_source, self.recon_normal, self.recon_branch, self.recon_reference,
            self.recon_payment, self.recon_virman, self.recon_review, self.recon_difference,
        )
        for index, cell in enumerate(self.recon_cells):
            recon_values.addWidget(cell, 0, index)
        recon_layout.addLayout(recon_values)
        root.addWidget(recon_panel)
        self.recon_panel = recon_panel

        # Source-file summary + live bank/category breakdown.  The source card
        # stays dominant, but the analytical card receives enough width to show
        # bank-level totals without clipping.
        overview_row = QGridLayout()
        overview_row.setSpacing(7)
        overview_row.setColumnStretch(0, 61)
        overview_row.setColumnStretch(1, 39)
        overview_row.setColumnMinimumWidth(1, 220)

        source_panel = QFrame()
        self.source_panel = source_panel
        source_panel.setObjectName("automationSourcePanel")
        source_panel.setFixedHeight(184)
        source_layout = QVBoxLayout(source_panel)
        source_layout.setContentsMargins(6, 3, 6, 3)
        source_layout.setSpacing(2)

        # Two-level header mirrors the approved mockup: identity and description
        # stay grouped on the left, while the compact controls form one aligned
        # toolbar on the right.  No empty spacer row is reserved above the table.
        source_head = QGridLayout()
        source_head.setContentsMargins(0, 0, 0, 0)
        source_head.setHorizontalSpacing(8)
        source_head.setVerticalSpacing(0)
        source_title_row = QHBoxLayout()
        source_title_row.setSpacing(6)
        source_icon = _label("", "automationSourceIcon")
        source_icon.setPixmap(workspace_icon("record", 19).pixmap(19, 19))
        source_title_row.addWidget(source_icon)
        source_title_row.addWidget(_label("Kaynak dosya özeti", "automationCompactTitle"))
        self.source_count_badge = _label("0 dosya", "automationCompactBadge")
        source_title_row.addWidget(self.source_count_badge)
        source_title_row.addStretch(1)
        source_head.addLayout(source_title_row, 0, 0)
        source_hint = _label("Bölgelere göre okunan kaynak dosyalarının özeti", "automationSourceHint")
        source_hint.setToolTip("Bölgelere göre okunan kaynak dosyalarının özeti")
        source_head.addWidget(source_hint, 1, 0)

        source_tools = QHBoxLayout()
        source_tools.setSpacing(5)
        self.file_region_filter = _PremiumComboBox()
        self.file_region_filter.setObjectName("sourceCompactFilter")
        self.file_region_filter.setMinimumContentsLength(7)
        self.file_region_filter.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.file_region_filter.addItem("Tüm bölgeler", None)
        self.file_region_filter.currentIndexChanged.connect(self._render_dashboard_sources)
        source_tools.addWidget(self.file_region_filter)
        self.file_search = QLineEdit()
        self.file_search.setObjectName("sourceCompactSearch")
        self.file_search.setPlaceholderText("Dosya ara…")
        self.file_search.setMinimumWidth(105)
        self.file_search.setMaximumWidth(145)
        self.file_search.textChanged.connect(self._render_dashboard_sources)
        source_tools.addWidget(self.file_search)
        self.open_sources_button = QPushButton("Tümünü gör")
        self.open_sources_button.setObjectName("automationCompactButton")
        self.open_sources_button.clicked.connect(lambda _checked=False: self.set_mode("sources"))
        source_tools.addWidget(self.open_sources_button)
        source_head.addLayout(source_tools, 0, 1, 2, 1, Qt.AlignRight | Qt.AlignVCenter)
        source_head.setColumnStretch(0, 1)
        source_layout.addLayout(source_head)

        self.dashboard_sources = _table(
            ["Bölge", "Banka", "Toplam kayıt", "Otomatik", "Aktarıldı", "Boş", "Giren", "Çıkan", "Toplam"],
            "dashboardSourceTable",
        )
        self.dashboard_sources.setFixedHeight(112)
        # The source card deliberately shares the row with the analytical
        # breakdown.  Fixed legacy widths made the table overflow and reduced
        # file names to one-letter ellipses when the inspector was open.
        # Keep the money/status columns compact and let the filename column own
        # every remaining pixel.
        self.dashboard_sources.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        source_header = self.dashboard_sources.horizontalHeader()
        source_header.setMinimumSectionSize(28)
        # Descriptive/count columns size to their compact contents; the three
        # monetary columns share every remaining pixel. This keeps all totals
        # visible when the inspector is open without horizontal scrolling.
        for column in range(6):
            source_header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        for column in (6, 7, 8):
            source_header.setSectionResizeMode(column, QHeaderView.Stretch)
        self.dashboard_sources.verticalHeader().setDefaultSectionSize(20)
        source_layout.addWidget(self.dashboard_sources, 1)
        overview_row.addWidget(source_panel, 0, 0)

        self.breakdown_panel = QFrame()
        self.breakdown_panel.setObjectName("automationPreviousPanel")
        self.breakdown_panel.setFixedHeight(184)
        breakdown_layout = QVBoxLayout(self.breakdown_panel)
        breakdown_layout.setContentsMargins(6, 3, 6, 3)
        breakdown_layout.setSpacing(2)

        breakdown_head = QHBoxLayout()
        breakdown_head.setSpacing(6)
        breakdown_icon = _label("", "automationBreakdownIcon")
        breakdown_icon.setPixmap(workspace_icon("workflow", 18).pixmap(18, 18))
        breakdown_head.addWidget(breakdown_icon)
        breakdown_head.addWidget(_label("Mevcut işlem dağılımı", "automationCompactTitle"))
        breakdown_head.addStretch(1)
        self.breakdown_total = _label("—", "automationBreakdownTotal")
        self.breakdown_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        breakdown_head.addWidget(self.breakdown_total)
        breakdown_layout.addLayout(breakdown_head)

        breakdown_filters = QGridLayout()
        breakdown_filters.setHorizontalSpacing(5)
        breakdown_filters.setVerticalSpacing(1)
        for column, title in enumerate(("Bölge", "Banka", "Kategori")):
            breakdown_filters.addWidget(_label(title, "automationBreakdownFilterLabel"), 0, column)
        self.breakdown_region = _PremiumComboBox()
        self.breakdown_region.setObjectName("breakdownFilter")
        self.breakdown_region.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.breakdown_region.setMinimumContentsLength(7)
        self.breakdown_region.currentIndexChanged.connect(self._render_current_breakdown)
        breakdown_filters.addWidget(self.breakdown_region, 1, 0)
        self.breakdown_bank = _PremiumComboBox()
        self.breakdown_bank.setObjectName("breakdownFilter")
        self.breakdown_bank.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.breakdown_bank.setMinimumContentsLength(7)
        self.breakdown_bank.currentIndexChanged.connect(self._render_current_breakdown)
        breakdown_filters.addWidget(self.breakdown_bank, 1, 1)
        self.breakdown_category = _PremiumComboBox()
        self.breakdown_category.setObjectName("breakdownFilter")
        self.breakdown_category.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.breakdown_category.setMinimumContentsLength(8)
        for key, label in CATEGORIES:
            if key != "review":
                self.breakdown_category.addItem(label, key)
        self.breakdown_category.currentIndexChanged.connect(self._render_current_breakdown)
        breakdown_filters.addWidget(self.breakdown_category, 1, 2)
        breakdown_filters.setColumnStretch(0, 1)
        breakdown_filters.setColumnStretch(1, 1)
        breakdown_filters.setColumnStretch(2, 1)
        breakdown_layout.addLayout(breakdown_filters)

        self.breakdown_context = _label("Banka bazlı dağılım", "automationBreakdownContext")
        breakdown_layout.addWidget(self.breakdown_context)
        self.breakdown_table = output_table(["Banka", "Kayıt", "Pay", "Tutar"])
        self.breakdown_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.breakdown_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.breakdown_table.verticalHeader().setDefaultSectionSize(19)
        self.breakdown_table.setMinimumWidth(0)
        self.breakdown_table.setFixedHeight(80)
        self.breakdown_table.setWordWrap(False)
        self.breakdown_table.setTextElideMode(Qt.ElideRight)
        self.breakdown_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.breakdown_table.setColumnWidth(0, 160)
        self.breakdown_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.breakdown_table.setColumnWidth(1, 44)
        self.breakdown_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.breakdown_table.setColumnWidth(2, 70)
        self.breakdown_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        breakdown_layout.addWidget(self.breakdown_table)
        self.breakdown_note = _label("Tutarlar seçili kategoriye aittir; pay yalnız bilinen tutarlardan hesaplanır.", "automationBreakdownNote")
        self.breakdown_note.hide()
        breakdown_layout.addWidget(self.breakdown_note)
        self.breakdown_button = QPushButton("Bölge ve çıktı ayrıntıları →")
        self.breakdown_button.setObjectName("automationCompactButton")
        self.breakdown_button.setFixedHeight(22)
        self.breakdown_button.clicked.connect(self.outputs_requested.emit)
        breakdown_layout.addWidget(self.breakdown_button)
        overview_row.addWidget(self.breakdown_panel, 0, 1)
        # Responsive guard: do not let the wider analytics card create a horizontal canvas overflow.
        overview_row.setColumnMinimumWidth(0, 0)
        overview_row.setColumnMinimumWidth(1, 220)
        source_panel.setMinimumWidth(0)
        self.breakdown_panel.setMinimumWidth(0)
        self.dashboard_sources.setMinimumWidth(0)
        self.breakdown_table.setMinimumWidth(0)
        source_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.breakdown_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        root.addLayout(overview_row)

        # Operational title and view tabs.  The warning marker is semantic,
        # matching the approved mockup without changing the queue logic.
        heading_col = QVBoxLayout()
        heading_col.setSpacing(1)
        review_title_row = QHBoxLayout()
        review_title_row.setSpacing(6)
        self.review_title_icon = _label("!", "automationReviewIcon")
        self.review_title_icon.setAlignment(Qt.AlignCenter)
        self.review_title_icon.setFixedSize(20, 20)
        review_title_row.addWidget(self.review_title_icon)
        review_title_row.addWidget(_label("Önce kontrol gerektiren kayıtlar", "automationSectionTitle"))
        review_title_row.addStretch(1)
        heading_col.addLayout(review_title_row)
        self.view_tabs = QHBoxLayout()
        self.view_tabs.setSpacing(4)
        self.attention_tab = QPushButton("Dikkat gerektiren  0")
        self.ready_tab = QPushButton("Hazır  0")
        self.all_tab = QPushButton("Tüm kayıtlar  0")
        for button, tone in ((self.attention_tab, "warning"), (self.ready_tab, "success"), (self.all_tab, "neutral")):
            button.setObjectName("automationViewTab")
            button.setProperty("tone", tone)
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.view_tabs.addWidget(button)
        self.view_tabs.addStretch(1)
        self.attention_tab.setChecked(True)
        self.attention_tab.clicked.connect(lambda: self._set_filter_mode("attention"))
        self.ready_tab.clicked.connect(lambda: self._set_filter_mode("ready"))
        self.all_tab.clicked.connect(lambda: self._set_filter_mode("all"))
        heading_col.addLayout(self.view_tabs)
        heading_panel = QWidget()
        heading_panel.setLayout(heading_col)
        heading_col.setContentsMargins(8, 6, 8, 0)
        heading_panel.setObjectName("reviewHeadingPanel")
        heading_panel.setMinimumHeight(54)
        overview_row.addWidget(heading_panel, 1, 0, 1, 2)

        # Filter toolbar.
        toolbar = QGridLayout()
        self.review_toolbar = toolbar
        toolbar.setSpacing(7)
        self.search = QLineEdit()
        self.search.setObjectName("automationSearch")
        self.search.setPlaceholderText("Müşteri, belge veya açıklama ara…")
        self.search.textChanged.connect(self.render_records)
        self.search.setMinimumWidth(0)
        toolbar.addWidget(self.search, 0, 0)
        self.region_filter = _PremiumComboBox()
        self.region_filter.setObjectName("automationFilter")
        self.region_filter.addItem("Tüm bölgeler", None)
        self.region_filter.currentIndexChanged.connect(self.render_records)
        self.region_filter.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.region_filter.setMinimumContentsLength(10)
        toolbar.addWidget(self.region_filter, 0, 1)
        self.source_filter = _PremiumComboBox()
        self.source_filter.setObjectName("automationFilter")
        self.source_filter.addItem("Tüm kaynaklar", None)
        self.source_filter.currentIndexChanged.connect(self.render_records)
        self.source_filter.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.source_filter.setMinimumContentsLength(10)
        toolbar.addWidget(self.source_filter, 0, 2)
        self.reason_filter = _PremiumComboBox()
        self.reason_filter.setObjectName("automationFilter")
        self.reason_filter.setMinimumContentsLength(12)
        self.reason_filter.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.reason_filter.addItem("Tüm kontrol nedenleri", None)
        self.reason_filter.currentIndexChanged.connect(self.render_records)
        toolbar.addWidget(self.reason_filter, 0, 3)
        filter_button = QPushButton("Filtreler")
        filter_button.setIcon(workspace_icon("filter", 16))
        filter_button.setObjectName("automationToolbarButton")
        filter_button.setToolTip("Bölge, kaynak, neden ve arama filtrelerini temizle")
        filter_button.clicked.connect(self._clear_record_filters)
        toolbar.addWidget(filter_button, 0, 4)
        view_button = QPushButton("Görünüm")
        view_button.setIcon(workspace_icon("columns", 16))
        view_button.setObjectName("automationToolbarButton")
        view_button.setToolTip("Görünen tablo sütunlarını seç")
        self.column_menu = QMenu(view_button)
        view_button.setMenu(self.column_menu)
        toolbar.addWidget(view_button, 0, 5)
        self.review_controls = (self.search, self.region_filter, self.source_filter, self.reason_filter, filter_button, view_button)
        self.inspector_open_button = QPushButton("Ayrıntı  ›")
        self.inspector_open_button.setObjectName("automationInspectorOpen")
        self.inspector_open_button.setToolTip("Kayıt ayrıntısı panelini aç")
        self.inspector_open_button.clicked.connect(lambda _checked=False: self.set_inspector_visible(True))
        self.inspector_open_button.hide()
        # The header already exposes Ayrıntı; retain this compatibility button
        # without adding another row to the compact filter rail.
        self.inspector_open_button.setParent(canvas)
        root.addLayout(toolbar)

        # Main table; the right inspector lives outside this canvas and spans
        # the entire page height, matching the approved layout.
        self.records = _table(["", "Durum", "Müşteri / Açıklama", "Bölge", "Kaynak", "Tutar", "Kontrol nedeni", "İşlem tarihi"])
        self.records.setObjectName("attentionTable")
        self.records.setSortingEnabled(False)
        self.records.setMinimumWidth(0)
        self.records.setColumnWidth(0, 26)
        self.records.setColumnWidth(1, 105)
        self.records.setColumnWidth(2, 245)
        self.records.setColumnWidth(3, 75)
        self.records.setColumnWidth(4, 92)
        self.records.setColumnWidth(5, 115)
        self.records.setColumnWidth(7, 120)
        self.records.verticalHeader().setDefaultSectionSize(30)
        self.records.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.records.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.records.itemSelectionChanged.connect(self.show_detail)
        self.records.cellClicked.connect(lambda _row, _column: self.set_inspector_visible(True))
        for column in range(1, self.records.columnCount()):
            action = self.column_menu.addAction(self.records.horizontalHeaderItem(column).text())
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(lambda checked, col=column: self.records.setColumnHidden(col, not checked))
        root.addWidget(self.records, 1)

        # Real, read-only pagination for the operational table.
        pager = QHBoxLayout()
        pager.setSpacing(6)
        self.record_range = _label("0 / 0 kayıt", "automationFooterText")
        pager.addWidget(self.record_range)
        pager.addStretch(1)
        pager.addWidget(_label("Satır sayısı", "automationFooterText"))
        self.page_size = _PremiumComboBox()
        self.page_size.setObjectName("automationPageSize")
        self.page_size.addItems(["25", "50", "100"])
        self.page_size.setCurrentText("50")
        self.page_size.setFixedWidth(62)
        self.page_size.currentTextChanged.connect(self._change_page_size)
        pager.addWidget(self.page_size)
        self.page_prev = QPushButton("‹")
        self.page_next = QPushButton("›")
        for button in (self.page_prev, self.page_next):
            button.setObjectName("automationPagerButton")
            button.setFixedSize(26, 22)
        self.page_prev.clicked.connect(lambda: self._change_page(-1))
        self.page_next.clicked.connect(lambda: self._change_page(1))
        pager.addWidget(self.page_prev)
        self.page_number = _label("1 / 1", "automationFooterText")
        pager.addWidget(self.page_number)
        pager.addWidget(self.page_next)
        root.addLayout(pager)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.runtime_status = _label("Yerel çalışma · Kaydedilmedi", "automationFooterText")
        footer.addWidget(self.runtime_status)
        footer.addStretch(1)
        root.addLayout(footer)

        self.canvas_scroll = QScrollArea()
        self.canvas_scroll.setObjectName("automationCanvasScroll")
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas_scroll.setFrameShape(QFrame.NoFrame)
        self.canvas_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.canvas_scroll.setWidget(canvas)
        shell.addWidget(self.canvas_scroll, 1)

        # Full-height inspector: this is intentionally a sibling of the left
        # canvas rather than a child of the table area.
        self.inspector_frame = QFrame()
        self.inspector_frame.setObjectName("inspectorPanel")
        self.inspector_frame.setMinimumWidth(320)
        self.inspector_frame.setMaximumWidth(320)
        self.inspector_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        inspector_layout = QVBoxLayout(self.inspector_frame)
        inspector_layout.setContentsMargins(9, 8, 9, 8)
        inspector_layout.setSpacing(4)
        inspector_header = QHBoxLayout()
        inspector_heading = QVBoxLayout()
        inspector_heading.setSpacing(1)
        inspector_heading.addWidget(_label("Kayıt ayrıntısı", "inspectorTitle"))
        self.inspector_count = _label("Kayıt seçilmedi", "inspectorMeta")
        inspector_heading.addWidget(self.inspector_count)
        inspector_header.addLayout(inspector_heading, 1)
        prev_button = QPushButton("‹")
        next_button = QPushButton("›")
        close_button = QPushButton("×")
        for button in (prev_button, next_button, close_button):
            button.setObjectName("inspectorNavButton")
            button.setFixedSize(22, 22)
        prev_button.clicked.connect(lambda: self._move_selection(-1))
        next_button.clicked.connect(lambda: self._move_selection(1))
        close_button.clicked.connect(lambda _checked=False: self.set_inspector_visible(False))
        close_button.setToolTip("Kayıt ayrıntısını kapat")
        inspector_header.addWidget(prev_button)
        inspector_header.addWidget(next_button)
        inspector_header.addWidget(close_button)
        inspector_layout.addLayout(inspector_header)

        self.inspector_status = _label("", "inspectorStatusPill")
        self.inspector_status.hide()
        inspector_layout.addWidget(self.inspector_status, 0, Qt.AlignLeft)

        self.record_summary = QLabel(self.inspector_frame)
        self.record_summary.setObjectName("inspectorRecordSummary")
        self.record_summary.setWordWrap(True)
        self.record_summary.setTextFormat(Qt.RichText)
        inspector_layout.addWidget(self.record_summary)

        self.inspector_tabs = QTabBar(self.inspector_frame)
        self.inspector_tabs.setObjectName("inspectorTabs")
        self.inspector_tabs.setExpanding(False)
        for title in ("Eşleştirme", "Kaynak", "İz kaydı", "Notlar"):
            self.inspector_tabs.addTab(title)
        self.inspector_tabs.currentChanged.connect(lambda _index: self.show_detail())
        inspector_layout.addWidget(self.inspector_tabs)
        self.inspector = QTextBrowser()
        self.inspector.setObjectName("recordInspector")
        self.inspector.setOpenExternalLinks(False)
        inspector_layout.addWidget(self.inspector, 1)
        self.evidence_scroll = QScrollArea()
        self.evidence_scroll.setObjectName("inspectorEvidenceScroll")
        self.evidence_scroll.setFrameShape(QFrame.NoFrame)
        self.evidence_scroll.setWidgetResizable(True)
        self.evidence_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        evidence = QWidget()
        evidence.setObjectName("inspectorEvidence")
        evidence.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        evidence_layout = QVBoxLayout(evidence)
        evidence_layout.setContentsMargins(0, 0, 0, 0)
        evidence_layout.setSpacing(4)
        evidence_layout.addWidget(_label("Neden bu kayıt?", "inspectorSectionTitle"))
        self.evidence_values = {}
        self.evidence_icons = {}
        for key, title in (("reason", "Kontrol nedeni"), ("rule", "Kural"), ("outcome", "Motor kararı"), ("source", "Kaynak kayıt")):
            line = QFrame()
            line.setObjectName("inspectorEvidenceRow")
            line_layout = QHBoxLayout(line)
            line_layout.setContentsMargins(0, 2, 0, 2)
            icon = _label("•", "inspectorEvidenceIcon")
            icon.setFixedSize(16, 16)
            icon.setAlignment(Qt.AlignCenter)
            line_layout.addWidget(icon)
            line_layout.addWidget(_label(title, "inspectorKey"), 2)
            value = _label("—", "inspectorValue", wrap=True)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            line_layout.addWidget(value, 3)
            self.evidence_values[key] = value
            self.evidence_icons[key] = icon
            evidence_layout.addWidget(line)
        confidence_row = QHBoxLayout()
        confidence_row.addWidget(_label("Eşleşme güveni", "inspectorKey"))
        confidence_row.addStretch(1)
        confidence_row.addWidget(_label("Güven verisi yok", "inspectorNeutral"))
        evidence_layout.addLayout(confidence_row)
        track = QFrame()
        track.setObjectName("confidenceUnavailable")
        track.setFixedHeight(5)
        track.setAccessibleName("Sayısal güven verisi mevcut değil")
        evidence_layout.addWidget(track)
        evidence_layout.addWidget(_label("Hedef kayıt", "inspectorSectionTitle"))
        target = QGridLayout()
        target.setVerticalSpacing(3)
        self.target_values = {}
        for index, (key, title) in enumerate((("adapter", "Çıktı adaptörü"), ("account", "Cari hesap"), ("rule", "Muhasebe kuralı"), ("amount", "Tutar"))):
            target.addWidget(_label(title, "inspectorKey"), index, 0)
            value = _label("—", "inspectorValue", wrap=True)
            target.addWidget(value, index, 1)
            self.target_values[key] = value
        self.target_values["amount"].setProperty("emphasis", "true")
        evidence_layout.addLayout(target)
        self.inspector_warning = _label("", "inspectorWarning", wrap=True)
        evidence_layout.addWidget(self.inspector_warning)
        evidence_layout.addStretch(1)
        self.evidence_scroll.setWidget(evidence)
        inspector_layout.addWidget(self.evidence_scroll, 1)
        self.matching_button = QPushButton("Eşleştirme ekranını aç")
        self.matching_button.setObjectName("primary")
        self.matching_button.setToolTip("Kararları mevcut Eşleştirme & Kurallar ekranında düzenleyin.")
        self.matching_button.clicked.connect(self.matching_requested.emit)
        inspector_layout.addWidget(self.matching_button)
        detail_actions = QHBoxLayout()
        for text, tab in (("Kaynağı göster", 1), ("İz kaydı", 2)):
            button = QPushButton(text)
            button.setObjectName("inspectorSecondary")
            button.clicked.connect(lambda _checked=False, index=tab: self.inspector_tabs.setCurrentIndex(index))
            detail_actions.addWidget(button)
        inspector_layout.addLayout(detail_actions)

        self.inspector_output_button = QPushButton("↗  Son çıktıları aç")
        self.inspector_output_button.setObjectName("inspectorOutputAction")
        self.inspector_output_button.clicked.connect(self.open_output_location)
        self.inspector_output_button.hide()

        self.preview_button = QPushButton("Planı önizle")
        self.preview_button.setObjectName("primary")
        self.preview_button.clicked.connect(lambda _checked=False: self.preview_requested.emit())
        self.output_button = QPushButton("Çıktıları hazırla")
        self.output_button.setObjectName("primary")
        self.output_button.clicked.connect(lambda _checked=False: self.output_requested.emit())
        self.preview_button.setEnabled(False)
        self.output_button.setEnabled(False)
        self.operation_actions = QFrame(page)
        self.operation_actions.setObjectName("operationActionBar")
        action_row = QHBoxLayout(self.operation_actions)
        action_row.setContentsMargins(10, 4, 10, 4)
        action_row.setSpacing(6)
        self.operation_hint = QLabel("Başlamak için kaynak ekleyin.", self.operation_actions)
        self.operation_hint.setWordWrap(True)
        action_row.addWidget(self.operation_hint, 1)
        action_row.addWidget(self.output_access)
        action_row.addWidget(self.inspector_output_button)
        action_row.addWidget(self.preview_button)
        action_row.addWidget(self.output_button)
        page_layout.addWidget(self.operation_actions)
        shell.addWidget(self.inspector_frame, 0)
        self._inspector_target_width = 320
        self._inspector_animation = QPropertyAnimation(self.inspector_frame, b"maximumWidth", self)
        self._inspector_animation.setDuration(190)
        self._inspector_animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._inspector_animation.finished.connect(self._inspector_animation_finished)
        self._inspector_open = True

        # Legacy filter compatibility. It is intentionally hidden; the mockup
        # uses the three visible view tabs above.
        self.filter = QComboBox(self)
        self.filter.addItems(["Önce istisnalar · tüm kayıtlar", "Yalnız kontrol gerektirenler"])
        self.filter.hide()
        self._filter_mode = "attention"
        self._page_index = 0
        self._page_size_value = 50
        return page

    def _clear_record_filters(self) -> None:
        self.search.clear()
        for combo in (self.region_filter, self.source_filter, self.reason_filter):
            combo.setCurrentIndex(0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_inspector_open") and self.width() < 950 and self._inspector_open:
            self.set_inspector_visible(False, animated=False)
        self._adapt_workspace_width()

    def _adapt_workspace_width(self) -> None:
        if not hasattr(self, "canvas_scroll"):
            return
        # Pass 23: match the mockup inspector proportion without penalising
        # smaller desktop widths.  The content stays unchanged; only the shell
        # allocation changes.
        desired_inspector_width = 356 if self.width() >= 1500 else 320
        if self._inspector_target_width != desired_inspector_width:
            self._inspector_target_width = desired_inspector_width
            if self._inspector_open and self.inspector_frame.isVisible():
                self.inspector_frame.setMinimumWidth(desired_inspector_width)
                self.inspector_frame.setMaximumWidth(desired_inspector_width)
        width = self.width() - (self._inspector_target_width if self._inspector_open else 0)
        compact = width < 880
        # Inspector-open desktops are wide enough to keep the approved single
        # KPI row, but not wide enough for the large full-width typography.
        # Switch only the text scale, never the data or card order.
        dense_metrics = bool(self._inspector_open and width < 1200 and not compact)
        for tile in self.metric_tiles:
            for widget in (tile.label, tile.value, tile.detail):
                widget.setProperty("dense", "true" if dense_metrics else "false")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            finance = tile.property("variant") == "finance"
            # The approved first-three KPI badge is a fixed 34 px circle even
            # with the inspector open; only their text switches to dense mode.
            icon_size = 38 if finance else (22 if dense_metrics else 24)
            tile.icon.setFixedSize(icon_size, icon_size)
        for column in range(6):
            self.review_toolbar.setColumnStretch(column, (1 if column < 3 else 0) if compact else (3 if column == 0 else (1 if column < 4 else 0)))
        for widget in self.review_controls:
            self.review_toolbar.removeWidget(widget)
        for index, widget in enumerate(self.review_controls):
            self.review_toolbar.addWidget(widget, index // (3 if compact else 6), index % (3 if compact else 6))
        self.summary_layout.removeItem(self.summary_actions)
        self.summary_layout.addLayout(self.summary_actions, 1 if compact else 0, 0 if compact else 3, 1, 3 if compact else 1)
        for layout, widgets, columns in (
            (self.metric_layout, self.metric_tiles, 4 if compact else 7),
            (self.recon_layout, self.recon_cells, 4 if compact else 8),
            (self.step_layout, self.steps, 3 if compact else 6),
        ):
            for widget in widgets:
                layout.removeWidget(widget)
            for index, widget in enumerate(widgets):
                layout.addWidget(widget, index // columns, index % columns)

        # At full desktop width the first three finance cards receive more room
        # than the four status cards.  Compact/reflowed layouts stay balanced.
        metric_stretches = (1, 1, 1, 1) if compact else (13, 13, 11, 10, 10, 10, 10)
        for column in range(7):
            self.metric_layout.setColumnStretch(
                column, metric_stretches[column] if column < len(metric_stretches) else 0
            )

        # Preserve every source fact on normal desktop widths.  Only at the
        # narrow responsive boundary do the two least critical receipt-count
        # columns collapse; their data remains in the model and returns as soon
        # as space is available.  This prevents horizontal overflow while
        # keeping filename/region/bank/financial facts readable.
        narrow_source = bool(self._inspector_open or width < 1180)
        self.dashboard_sources.setColumnHidden(4, narrow_source)  # Aktarıldı
        self.dashboard_sources.setColumnHidden(5, narrow_source)  # Boş
        self.step_note.setVisible(not compact)
        self.step_layout.addWidget(self.step_note, 0 if not compact else 2, 6 if not compact else 0)

    def set_inspector_visible(self, visible: bool, *, animated: bool = True) -> None:
        """Collapse/expand the context panel without changing record state."""
        visible = bool(visible)
        if visible == self._inspector_open and self.inspector_frame.isVisible() == visible:
            return
        self._inspector_open = visible
        self.detail_toggle.setChecked(visible)
        self.detail_toggle.setVisible(not visible)
        self._adapt_workspace_width()
        self._inspector_animation.stop()
        if visible:
            self.inspector_frame.setMinimumWidth(0)
            self.inspector_frame.show()
            self.inspector_open_button.hide()
            start = max(0, self.inspector_frame.width())
            end = self._inspector_target_width
        else:
            self.inspector_frame.setMinimumWidth(0)
            self.inspector_open_button.hide()
            start = max(self.inspector_frame.width(), self._inspector_target_width)
            end = 0
        if not animated:
            self.inspector_frame.setMaximumWidth(end)
            self.inspector_frame.setMinimumWidth(self._inspector_target_width if visible else 0)
            if not visible:
                self.inspector_frame.hide()
            return
        if not visible:
            # Closing must reach a deterministic hidden state immediately.
            # The previous animated close could finish late under a busy Qt
            # event loop and allow render_records() to observe a visible frame.
            self.inspector_frame.setMaximumWidth(0)
            self.inspector_frame.setMinimumWidth(0)
            self.inspector_frame.hide()
            return
        self._inspector_animation.setStartValue(start)
        self._inspector_animation.setEndValue(end)
        self._inspector_animation.start()

    def _inspector_animation_finished(self) -> None:
        if not self._inspector_open:
            self.inspector_frame.hide()
        else:
            self.inspector_frame.setMaximumWidth(self._inspector_target_width)
            self.inspector_frame.setMinimumWidth(self._inspector_target_width)

    def _change_page_size(self, value: str) -> None:
        try:
            self._page_size_value = max(1, int(value))
        except (TypeError, ValueError):
            self._page_size_value = 50
        self._page_index = 0
        self.render_records()

    def _change_page(self, delta: int) -> None:
        total = len(getattr(self, "_filtered_rows", ()))
        pages = max(1, (total + self._page_size_value - 1) // self._page_size_value)
        self._page_index = min(max(0, self._page_index + delta), pages - 1)
        self.render_records()

    def _build_sources_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("automationSourcesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(_label("Kaynaklar ve mutabakat", "automationPageTitle"))
        title.addWidget(_label("Yüklenen dosyaları, dağılımı ve önceki operasyonu inceleyin.", "automationPageSubtitle"))
        top.addLayout(title, 1)
        back = QPushButton("← Yeni çalışmaya dön")
        back.setObjectName("secondary")
        back.clicked.connect(lambda: self.set_mode("new"))
        top.addWidget(back)
        layout.addLayout(top)

        self.sources = _table(
            ["Kaynak dosyası", "Adaptör", "Bölge", "Banka", "Kayıt", "Dekont durumu / adet", "Kaynak tutarı"],
            "sourceSummaryTable",
        )
        self.sources.setMinimumHeight(220)
        self.sources.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self.sources, 2)

        bottom = QSplitter(Qt.Horizontal)
        self.reconciliation = QTextBrowser()
        self.reconciliation.setObjectName("reconciliationPanel")
        self.previous = QLabel()
        self.previous.setObjectName("previousOperationPanel")
        self.previous.setWordWrap(True)
        self.previous.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        bottom.addWidget(self.reconciliation)
        bottom.addWidget(self.previous)
        bottom.setStretchFactor(0, 2)
        bottom.setStretchFactor(1, 1)
        layout.addWidget(bottom, 1)
        return page

    # ------------------------------------------------------------ public state
    @property
    def is_busy(self):
        return self._thread is not None or self._busy

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.stack.setCurrentWidget(self.sources_page if mode in {"sources", "overview"} else self.new_page)

    def set_filter_mode(self, mode: str) -> None:
        self._set_filter_mode(mode)

    def set_busy(self, busy: bool, text: str | None = None) -> None:
        self._busy = bool(busy)
        if text:
            self.runtime_status.setText(text)
        has_sources = bool(self.view.sources)
        self.add_source_button.setEnabled(not busy)
        self.clear_source_button.setEnabled(has_sources and not busy)
        self.preview_button.setEnabled(has_sources and not busy)
        self.output_button.setEnabled(has_sources and not busy)
        if busy:
            self.output_button.setText("İşleniyor…")
        elif self._output_done:
            self.output_button.setText("Yeniden çıktı oluştur")
        else:
            self.output_button.setText("Çıktıları hazırla")
        self.preview_button.setText("Bekleyin…" if busy else "Planı önizle")
        if busy:
            self.header_state.setText("İşleniyor")
            self.header_state.setProperty("state", "busy")
            self.step_note.setText("Muhasebe kararı hazırlanıyor…")
        elif has_sources:
            self.header_state.setText("Hazır")
            self.header_state.setProperty("state", "ready")
        else:
            self.header_state.setText("Kaynak bekleniyor")
            self.header_state.setProperty("state", "idle")
        self.header_state.style().unpolish(self.header_state)
        self.header_state.style().polish(self.header_state)
        self._refresh_operation_actions()

    def _refresh_operation_actions(self) -> None:
        has_sources = bool(self.view.sources)
        busy = self.is_busy
        self.preview_button.setEnabled(has_sources and not busy)
        self.output_button.setEnabled(has_sources and not busy and (self._preview or self._output_done))
        self.preview_button.setObjectName("secondary" if self._preview or self._output_done else "primary")
        if busy:
            hint = "İşlem sürüyor; sonuçlar burada gösterilecek."
            label = "İşleniyor…"
        elif self._output_done:
            hint = f"Çıktı hazır · {len(self._last_created_files)} dosya"
            label = "Yeniden çıktı oluştur"
        elif self._preview:
            hint = (f"{self._unresolved_count} kayıt için işlem sırasında kararınız alınacak."
                    if self._unresolved_count else "Plan hazır. Çıktıları oluşturabilirsiniz.")
            label = f"{self._unresolved_count} karar · Devam et" if self._unresolved_count else "Çıktıları hazırla"
        else:
            hint = "Çıktı oluşturmadan önce planı önizleyin." if has_sources else "Başlamak için kaynak ekleyin."
            label = "Çıktıları hazırla"
        self.operation_hint.setText(hint)
        self.output_button.setText(label)
        self.preview_button.style().unpolish(self.preview_button)
        self.preview_button.style().polish(self.preview_button)

    def set_runtime_status(self, text: str) -> None:
        self.runtime_status.setText(text)
        lowered = text.casefold()
        if "tamamlanamadı" in lowered or "okunamadı" in lowered:
            self.header_state.setText("Hata")
            self.header_state.setProperty("state", "error")
        elif "hazır" in lowered or "tamamlandı" in lowered or "okundu" in lowered:
            self.header_state.setText("Hazır")
            self.header_state.setProperty("state", "ready")
        elif "bekleniyor" in lowered and not self.view.sources:
            self.header_state.setText("Kaynak bekleniyor")
            self.header_state.setProperty("state", "idle")
        self.header_state.style().unpolish(self.header_state)
        self.header_state.style().polish(self.header_state)

    def _refresh_output_access(self) -> None:
        if not hasattr(self, "output_access"):
            return
        available = bool(self._output_done and self._last_output_dir)
        self.output_access.setVisible(available)
        if hasattr(self, "inspector_output_button"):
            self.inspector_output_button.setVisible(available)
            self.inspector_output_button.setEnabled(available)
            self.inspector_output_button.setToolTip(str(self._last_output_dir) if available else "")
        if available:
            count = len(self._last_created_files)
            self.output_access_label.setText(
                f"{count} çıktı hazır" if count else "Çıktı hazır"
            )
            self.open_output_button.setEnabled(True)
            self.open_output_button.setToolTip(str(self._last_output_dir))
        else:
            self.open_output_button.setEnabled(False)
            self.open_output_button.setToolTip("")

    def open_output_location(self) -> None:
        target = self._last_output_dir
        if target is None:
            return
        target = Path(target)
        if not target.exists():
            self.set_runtime_status("Çıktı klasörü artık bulunamıyor")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def load(self, paths):
        self._pending = tuple(paths)
        self.summary, self.audits, self._operation_id = None, (), None
        self._preview = False
        self._output_done = False
        self._last_output_dir = None
        self._last_created_files = ()
        self._unresolved_count = 0
        self._refresh_output_access()
        self.set_runtime_status("Kaynaklar hazırlanıyor…" if paths else "Yerel çalışma · Kaynak bekleniyor")
        if self._thread is not None:
            return
        if not paths:
            self.view = AccountingView()
            self.set_busy(False)
            self.render()
            return
        self._active = tuple(paths)
        self._thread = QThread(self)
        active = self._active
        self._worker = BackgroundWorker(lambda: load_sources(active, self.paths.resource_root, self.paths.data_root))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._loaded)
        self._worker.failed.connect(self._failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._finished)
        self._thread.start()

    def _loaded(self, view):
        if self._active == self._pending:
            self.view = view
            self.set_runtime_status("Yerel çalışma · Kaynaklar okundu")
            self.render()
            self.sources_ready.emit()

    def _failed(self, error):
        self.view = AccountingView()
        self.render()
        self.facts.setText(f"Kaynak özeti okunamadı: {error}")
        self.set_runtime_status(f"Kaynak özeti okunamadı: {error}")

    def _finished(self):
        self._thread = None
        self._worker = None
        self.set_busy(False)
        if self._active != self._pending:
            self.load(self._pending)

    def set_result(self, result, *, preview, operation_id=None):
        self.summary = result.simulation_summary
        self.audits = tuple(result.decision_audits)
        self._operation_id = operation_id
        self._preview = bool(preview)
        self._output_done = not preview
        if not preview:
            self._last_created_files = tuple(Path(path) for path in getattr(result, "created_files", ()) or ())
            output_dir = getattr(result, "output_dir", None)
            if output_dir is None and self._last_created_files:
                output_dir = self._last_created_files[0].parent
            self._last_output_dir = Path(output_dir) if output_dir else None
        self._unresolved_count = int(getattr(result, "unresolved", 0) or 0)
        self._refresh_output_access()
        if preview:
            self.set_runtime_status("Yerel çalışma · Plan önizlemesi hazır")
        else:
            self.set_runtime_status(f"Yerel çalışma · {len(result.created_files)} çıktı kaydı oluşturuldu")
        observed = None
        if not preview and self.operation_reader and operation_id is not None:
            try:
                observed = self.operation_reader.get_operation_view(operation_id)
            except Exception:
                # Operation outputs are already finalized at this point.  A
                # read-only observability failure must never leave the local
                # workflow looking stuck or change accounting state.
                observed = None
        if observed:
            self.set_runtime_status(
                f"Geçmiş {observed.history_status} · Yayın {observed.publication_status or 'Kayıt yok'} · "
                f"İnceleme {observed.pending_review_count} · {observed.consistency_status}"
            )
        self.set_busy(False)
        self.header_state.setText("Tamamlandı" if not preview else "Önizleme hazır")
        self.header_state.setProperty("state", "ready")
        self.header_state.style().unpolish(self.header_state)
        self.header_state.style().polish(self.header_state)
        self.render()

    # ---------------------------------------------------------------- render
    def render(self):
        rows = detail_rows(self.view, self.audits)
        outcomes = Counter(r.outcome for r in rows if r.outcome)
        issues = sum(bool(r.issue) for r in rows)
        unknown = sum(r.region == "BILINMEYEN_BOLGE" for r in rows)
        regions = {r.region for r in rows if r.region != "BILINMEYEN_BOLGE"}

        # Compatibility text used by focused tests and diagnostics.
        self.status_summary.setText(
            f"Kaynak hatası: {issues} kayıt · "
            + (" · ".join(f"{key}: {count} kayıt" for key, count in sorted(outcomes.items()))
               if outcomes else "Muhasebe kararları henüz hesaplanmadı.")
        )
        self.facts.setText(
            f"{len(self.view.sources)} kaynak dosya · {len(regions)} bilinen bölge · {len(rows)} kayıt"
            + (f" · {unknown} kayıtta bölge henüz çözülemedi" if unknown else "")
        )
        if self.summary is None:
            self.financial.setText(
                "Kaynak tutarı: " + money_text(self.view.total)
                + " · Giriş/çıkış ve kararlar motor önizlemesi sonrası kullanılabilir."
            )
        else:
            s = self.summary
            self.financial.setText(
                f"Motor kapsamı · Giriş: {money_text(s.total('incoming_total'))} · "
                f"Çıkış: {money_text(s.total('outgoing_total'))} · Net: {money_text(s.manim_total)}"
            )

        self.source_stat.set_value(
            f"{len(self.view.sources)} kaynak dosya",
            " · ".join(sorted({s.adapter for s in self.view.sources})) or "Excel",
        )
        region_detail = "Kaynaklar otomatik sınıflandırıldı" if rows else "Kaynaklar otomatik sınıflandırılır"
        self.region_stat.set_value(f"{len(regions)} bölge", region_detail)
        self.record_stat.set_value(f"{len(rows):,}".replace(",", ".") + " kayıt", "Muhasebe hareketi")
        operation_day = _operation_day_text(rows)
        self.page_subtitle.setText(
            "Yeni çalışma · Kaynakları ekleyerek başlayın" if not rows
            else (f"Günlük aktarım · {operation_day}" if operation_day else f"Yeni çalışma · {len(self.view.sources)} kaynak dosya")
        )
        self.clear_source_button.setVisible(bool(self.view.sources))
        self.clear_source_button.setEnabled(bool(self.view.sources) and not self.is_busy)

        self._render_steps(rows)
        counts = self._decision_counts(rows)
        self._render_decision_summary(counts, len(rows))
        self._render_metric_strip(rows, counts)
        self._render_dashboard_reconciliation()
        self._render_dashboard_sources()
        self._render_current_breakdown()
        self._refresh_filters(rows)
        self._render_sources()
        self.render_records()
        self._render_reconciliation()
        self._render_previous()
        self._refresh_output_access()
        self._refresh_operation_actions()

    def _render_steps(self, rows) -> None:
        if not rows:
            active = 0
        elif self.summary is None:
            active = 2
        elif self._output_done:
            # Output publication is the terminal workflow state.  Special
            # routed records (payment-approved/reference) may remain visible
            # in the table but must not pull a completed run back to Review.
            active = len(self.steps)
        elif self._unresolved_count > 0 or getattr(self.summary, "needs_attention", False):
            active = 3
        else:
            active = 4
        for index, step in enumerate(self.steps):
            step.set_state("complete" if index < active else "active" if index == active else "pending")
        if not rows:
            self.step_note.setText("Kaynak bekleniyor")
        elif self.summary is None:
            self.step_note.setText(f"{len(self.view.sources)}/{len(self.view.sources)} dosya okundu · Önizleme bekleniyor")
        elif self._output_done:
            self.step_note.setText("Muhasebe çıktısı hazırlandı")
        else:
            self.step_note.setText("Motor önizlemesi tamamlandı")

    @staticmethod
    def _decision_counts(rows) -> tuple[int, int, int, int]:
        automatic = review = manual = invalid = 0
        for row in rows:
            if row.issue or row.outcome == "SKIPPED":
                invalid += 1
            elif row.outcome == "REVIEW":
                review += 1
            elif row.outcome == "MANUAL_HAVALE":
                manual += 1
            elif row.outcome:
                # REFERANSLI / ODEME_ONAYLANDI are completed routed outcomes,
                # not pending manual review.
                automatic += 1
        return automatic, review, manual, invalid

    def _render_decision_summary(self, counts, total: int) -> None:
        automatic, review, manual, invalid = counts
        self.legend_auto.text.setText(f"{automatic:,}".replace(",", ".") + " otomatik işlendi")
        self.legend_review.text.setText(f"{review:,}".replace(",", ".") + " eşleştirme kontrolü")
        self.legend_manual.text.setText(f"{manual:,}".replace(",", ".") + " manuel inceleme")
        self.legend_error.text.setText(f"{invalid:,}".replace(",", ".") + " eksik / geçersiz")
        self.decision_total.setText(f"{total:,}".replace(",", ".") + " kayıt")
        self.decision_bar.set_counts(counts)
        attention = review + manual + invalid
        ready = automatic
        self.attention_tab.setText(f"Dikkat gerektiren  {attention:,}".replace(",", "."))
        self.ready_tab.setText(f"Hazır  {ready:,}".replace(",", "."))
        self.all_tab.setText(f"Tüm kayıtlar  {total:,}".replace(",", "."))
        for button in (self.attention_tab, self.ready_tab, self.all_tab):
            button.ensurePolished()
            font = QFont(button.font())
            font.setBold(True)
            button.setMinimumWidth(QFontMetrics(font).horizontalAdvance(button.text()) + 24)
            button.setMinimumHeight(QFontMetrics(font).height() + 14)

    @staticmethod
    def _decision_amounts(rows) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        automatic = review = manual = invalid = Decimal("0.00")
        for row in rows:
            amount = row.amount if row.amount is not None else Decimal("0.00")
            if row.issue or row.outcome == "SKIPPED":
                invalid += amount
            elif row.outcome == "REVIEW":
                review += amount
            elif row.outcome == "MANUAL_HAVALE":
                manual += amount
            elif row.outcome:
                automatic += amount
        return automatic, review, manual, invalid

    def _render_metric_strip(self, rows, counts) -> None:
        if self.summary is None:
            self.metric_incoming.set_value("—", "Önizleme sonrası")
            self.metric_outgoing.set_value("—", "Önizleme sonrası")
            self.metric_net.set_value("—", "Önizleme sonrası")
        else:
            self.metric_incoming.set_value(_amount_text(self.summary.total("incoming_total")), "Kaynak hareketleri")
            self.metric_outgoing.set_value(_amount_text(self.summary.total("outgoing_total")), "Kaynak hareketleri")
            self.metric_net.set_value(_amount_text(self.summary.manim_total), "Net kaynak hareketi")

        amounts = self._decision_amounts(rows)
        labels = (self.metric_auto, self.metric_review, self.metric_manual, self.metric_invalid)
        for tile, count, amount in zip(labels, counts, amounts):
            tile.progress.setValue(round(100 * count / len(rows)) if rows else 0)
            if self.audits or any(r.issue for r in rows):
                tile.set_value(
                    f"{count:,}".replace(",", ".") + " kayıt",
                    _amount_text(amount),
                )
            else:
                tile.set_value("—", "Önizleme sonrası")

    def _render_dashboard_reconciliation(self) -> None:
        result = reconcile(self.view, self.summary)
        self.recon_source.set_value(_amount_text(result.source_total))
        if self.summary is None:
            for cell in (
                self.recon_normal, self.recon_branch, self.recon_reference, self.recon_payment,
                self.recon_virman, self.recon_review, self.recon_difference,
            ):
                cell.set_value("—")
            return

        branch = self.summary.branch_output_total
        self.recon_branch.set_value(_amount_text(branch))
        self.recon_normal.set_value(_amount_text(self.summary.netsis_total - branch) if branch is not None else "—")
        self.recon_branch.setToolTip("Üretilen şubeli tahsilat ve birleşik banka hareketi satırlarının toplamı. Manuel eşleştirmeler normal havalede yer alır.")
        self.recon_normal.setToolTip("Şubeli dışındaki hazırlanmış havale satırları. Çıktı satırı dökümü yoksa ayrım bilinmez.")
        virman_details = [d for b in self.summary.buckets for d in b.details if d.outcome in {'VIRMAN', 'SAME_BANK_VIRMAN'}]
        virman_complete = all(len(b.details) == b.record_count for b in self.summary.buckets)
        virman_volume = sum((abs(d.amount) for d in virman_details), Decimal(0)) if virman_complete else None
        self.recon_virman.set_value(_amount_text(virman_volume))
        self.recon_virman.setToolTip(
            f"Hareket hacmi: giriş ve çıkışların mutlak toplamı. İşaretli net: {_amount_text(self.summary.total('virman_total'))}."
            if virman_complete else "Hareket ayrıntıları bulunmadığı için mutlak hacim bilinmiyor."
        )
        for cell, outcome, field in (
            (self.recon_reference, "REFERANSLI", "reference_total"),
            (self.recon_payment, "ODEME_ONAYLANDI", "payment_total"),
            (self.recon_review, "REVIEW", "review_total"),
        ):
            details = [d for b in self.summary.buckets for d in b.details if d.outcome == outcome]
            complete = all(len(b.details) == b.record_count for b in self.summary.buckets)
            gross = sum((abs(d.amount) for d in details), Decimal(0)) if complete else None
            cell.set_value(_amount_text(gross))
            cell.setToolTip(f"Hareket hacmi: giriş ve çıkışların mutlak toplamı. İşaretli net: {_amount_text(self.summary.total(field))}." if complete else "Hareket ayrıntıları bulunmadığı için mutlak hacim bilinmiyor.")
        self.recon_difference.set_value(_amount_text(result.difference))
        difference_ok = result.difference == Decimal("0.00") and not any(b.unaccounted_total for b in self.summary.buckets)
        self.recon_difference.setProperty("tone", "success" if difference_ok else "warning")
        self.recon_difference.setToolTip(result.limitation)
        self.recon_difference.style().unpolish(self.recon_difference)
        self.recon_difference.style().polish(self.recon_difference)

    def _render_dashboard_sources(self) -> None:
        current = self.file_region_filter.currentData()
        regions = sorted({r.region for s in self.view.sources for r in s.records if r.region})
        self.file_region_filter.blockSignals(True)
        self.file_region_filter.clear()
        self.file_region_filter.addItem("Tüm bölgeler", None)
        for region in regions:
            self.file_region_filter.addItem(region, region)
        self.file_region_filter.setCurrentIndex(max(0, self.file_region_filter.findData(current)))
        self.file_region_filter.blockSignals(False)
        self.source_count_badge.setText(f"{len(self.view.sources)} dosya")
        query = self.file_search.text().casefold()
        selected_region = self.file_region_filter.currentData()
        visible_sources = tuple(s for s in self.view.sources
            if query in Path(s.path).name.casefold()
            and (not selected_region or any(r.region == selected_region for r in s.records)))
        # Pass 23: compact source summary shows only MANIM operational rows.
        # FOM/tahsilat and customer-list inputs still count in the source badge,
        # but must not render as empty region rows in this operational table.
        visible_sources = tuple(
            source for source in visible_sources
            if source.adapter == "MANİM Excel" and source.records
        )
        self.dashboard_sources.setRowCount(len(visible_sources))
        for n, source in enumerate(visible_sources):
            receipts = Counter((record.receipt or "").strip().casefold() for record in source.records)
            automatic = sum(count for key, count in receipts.items() if "otomatik" in key and "aktar" in key)
            transferred = sum(count for key, count in receipts.items() if "aktar" in key and "otomatik" not in key)
            blank = receipts.get("", 0)
            regions = sorted({r.region for r in source.records if r.region and r.region != "BILINMEYEN_BOLGE"})
            banks = sorted({r.bank for r in source.records if r.bank})
            supported = source.adapter == "MANİM Excel" and source.total is not None
            incoming = sum((r.amount for r in source.records if r.amount is not None and r.amount > 0), Decimal(0))
            outgoing = sum((-r.amount for r in source.records if r.amount is not None and r.amount < 0), Decimal(0))
            bank_names = [_display_bank_name(bank) for bank in banks]
            bank_summary = (
                "—" if not bank_names else bank_names[0] if len(bank_names) == 1 else f"{len(bank_names)} banka"
            )
            values = (
                ", ".join(regions) or "—",
                bank_summary,
                str(len(source.records)),
                str(automatic),
                str(transferred),
                str(blank),
                _amount_text(incoming) if supported else "—",
                _amount_text(outgoing) if supported else "—",
                _amount_text(source.total) if source.adapter == "MANİM Excel" else "—",
            )
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c == 0:
                    tooltip = f"{Path(source.path).name}\nBölge: {value}"
                elif c == 1:
                    tooltip = f"{Path(source.path).name}\nBankalar: {', '.join(bank_names) or '—'}"
                else:
                    tooltip = value
                item.setToolTip(tooltip)
                if c >= 2:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == 0:
                    item.setForeground(QColor('#2E4D74'))
                    font = item.font(); font.setBold(True); item.setFont(font)
                elif c == 1:
                    item.setForeground(QColor('#315BE8'))
                elif c == 3:
                    item.setForeground(QColor('#0A9D63'))
                    font = item.font(); font.setBold(True); item.setFont(font)
                elif c == 4:
                    item.setForeground(QColor('#315BE8'))
                elif c == 5 and value not in {'0', '—'}:
                    item.setForeground(QColor('#B66B00'))
                elif c in (6, 7, 8):
                    item.setForeground(QColor({6: '#087A61', 7: '#536987', 8: '#243B66'}[c]))
                    if c == 8:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                self.dashboard_sources.setItem(n, c, item)

    def _render_current_breakdown(self) -> None:
        rows = bank_breakdown(self.summary)

        # Preserve an explicit user selection, but default to the analytical
        # all-banks view.  The previous implementation could land on the sole
        # bank during rebuilds, which hid the intended bank-by-bank overview.
        selected_region = self.breakdown_region.currentData() if self.breakdown_region.currentIndex() > 0 else None
        regions = sorted({row['region'] for row in rows if row.get('region')})
        self.breakdown_region.blockSignals(True)
        self.breakdown_region.clear()
        self.breakdown_region.addItem('Tüm bölgeler', None)
        for region in regions:
            self.breakdown_region.addItem(region, region)
        region_index = self.breakdown_region.findData(selected_region) if selected_region is not None else 0
        self.breakdown_region.setCurrentIndex(region_index if region_index >= 0 else 0)
        self.breakdown_region.blockSignals(False)
        selected_region = self.breakdown_region.currentData() if self.breakdown_region.currentIndex() > 0 else None

        region_rows = [row for row in rows if not selected_region or row['region'] == selected_region]
        selected_bank = self.breakdown_bank.currentData() if self.breakdown_bank.currentIndex() > 0 else None
        banks = sorted({row['bank'] for row in region_rows if row.get('bank')})
        self.breakdown_bank.blockSignals(True)
        self.breakdown_bank.clear()
        self.breakdown_bank.addItem('Tüm bankalar', None)
        for bank in banks:
            self.breakdown_bank.addItem(_display_bank_name(bank), bank)
        bank_index = self.breakdown_bank.findData(selected_bank) if selected_bank is not None else 0
        self.breakdown_bank.setCurrentIndex(bank_index if bank_index >= 0 else 0)
        self.breakdown_bank.blockSignals(False)
        selected_bank = self.breakdown_bank.currentData() if self.breakdown_bank.currentIndex() > 0 else None

        category = self.breakdown_category.currentData() or 'normal'
        category_label = next((label for key, label in CATEGORIES if key == category), 'Havale')
        visible = [row for row in region_rows if not selected_bank or row['bank'] == selected_bank]

        # Multiple regions may share a bank.  Amount evidence keeps the same
        # conservative semantics as bank_breakdown(); record counts are merely
        # scope counts and never participate in accounting totals.
        aggregates: dict[str, dict[str, Decimal | int | None]] = {}
        for row in visible:
            bank = row['bank']
            current = aggregates.setdefault(bank, {'amount': Decimal(0), 'known': True, 'records': 0})
            current['records'] = int(current['records']) + int(row.get('record_count') or 0)
            value = row.get(category)
            if value is None:
                current['known'] = False
            elif bool(current['known']):
                current['amount'] = Decimal(current['amount']) + value

        ordered = sorted(aggregates.items(), key=lambda item: _display_bank_name(item[0]))
        known_values = [Decimal(info['amount']) for _bank, info in ordered if bool(info['known'])]
        known_total = sum(known_values, Decimal(0)) if known_values else Decimal(0)
        all_known = bool(ordered) and all(bool(info['known']) for _bank, info in ordered)

        self.breakdown_table.setRowCount(len(ordered))
        for n, (bank, info) in enumerate(ordered):
            amount = Decimal(info['amount']) if bool(info['known']) else None
            bank_item = QTableWidgetItem("")
            bank_item.setData(Qt.UserRole, _display_bank_name(bank))
            bank_item.setToolTip(_display_bank_name(bank))
            bank_font = bank_item.font(); bank_font.setBold(True); bank_item.setFont(bank_font)
            self.breakdown_table.setItem(n, 0, bank_item)
            # Pass 8 bank branding must be attached to the visible first cell.
            # The backing QTableWidgetItem remains in place for selection,
            # accessibility and tests; the cell widget is presentation only.
            self.breakdown_table.setCellWidget(n, 0, _bank_cell(bank, self.paths.resource_root))

            count_item = QTableWidgetItem(str(int(info['records'])))
            count_item.setTextAlignment(Qt.AlignCenter)
            count_item.setToolTip('Bu banka kapsamındaki kaynak/motor kayıt sayısı.')
            self.breakdown_table.setItem(n, 1, count_item)

            share = None if amount is None or known_total <= 0 else int((amount / known_total * 100).quantize(Decimal('1')))
            share_host = QWidget()
            share_layout = QHBoxLayout(share_host)
            share_layout.setContentsMargins(3, 1, 3, 1)
            progress = QProgressBar()
            progress.setObjectName('breakdownShare')
            progress.setRange(0, 100)
            progress.setValue(share or 0)
            progress.setTextVisible(share is not None)
            progress.setFormat('—' if share is None else f'%{share}')
            progress.setToolTip('Pay hesaplanamıyor.' if share is None else f'Seçili kategori toplamının %{share} kadarı.')
            share_layout.addWidget(progress)
            self.breakdown_table.setCellWidget(n, 2, share_host)
            share_marker = QTableWidgetItem('' if share is not None else '—')
            share_marker.setTextAlignment(Qt.AlignCenter)
            self.breakdown_table.setItem(n, 2, share_marker)

            amount_item = QTableWidgetItem(_amount_text(amount))
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setToolTip(
                _amount_text(amount) if amount is not None
                else 'Bu banka/kategori ayrıntısı henüz mevcut değil.'
            )
            amount_font = amount_item.font(); amount_font.setBold(True); amount_item.setFont(amount_font)
            amount_item.setForeground(QColor('#173F8A'))
            self.breakdown_table.setItem(n, 3, amount_item)
            self.breakdown_table.setRowHeight(n, 19)

        total = known_total if all_known else None
        self.breakdown_total.setText(_amount_text(total))
        region_text = selected_region or 'Tüm bölgeler'
        bank_scope = _display_bank_name(selected_bank) if selected_bank else f'{len(ordered)} banka'
        self.breakdown_context.setText(f'{category_label} · {bank_scope} · {region_text}')
        self.breakdown_note.setVisible(bool(ordered))

        # PASS27-DYNAMIC-BREAKDOWN-BEGIN
        # Compute the viewport from real Qt geometry instead of a hard-coded
        # height. Up to three banks must be fully visible on Windows/DPI.
        bank_row_count = self.breakdown_table.rowCount()
        visible_bank_rows = min(bank_row_count, 3)

        for bank_row in range(bank_row_count):
            self.breakdown_table.setRowHeight(bank_row, 19)

        header = self.breakdown_table.horizontalHeader()
        header_height = max(15, header.sizeHint().height(), header.height())
        rows_height = sum(
            max(19, self.breakdown_table.rowHeight(bank_row))
            for bank_row in range(visible_bank_rows)
        )
        frame_height = self.breakdown_table.frameWidth() * 2
        table_height = header_height + rows_height + frame_height + 3

        if bank_row_count <= 3:
            self.breakdown_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        else:
            self.breakdown_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.breakdown_table.setFixedHeight(table_height)

        breakdown_help = (
            "Tutarlar se??ili kategoriye aittir; "
            "pay yaln??z bilinen tutarlardan hesaplan??r."
        )
        self.breakdown_table.setToolTip(breakdown_help)
        self.breakdown_note.setToolTip(breakdown_help)
        self.breakdown_note.setMinimumHeight(0)
        self.breakdown_note.setMaximumHeight(0)
        self.breakdown_note.hide()
        # PASS27-DYNAMIC-BREAKDOWN-END


    def _refresh_filters(self, rows) -> None:
        reason = self.reason_filter.currentData()
        self.reason_filter.blockSignals(True)
        self.reason_filter.clear()
        self.reason_filter.addItem("Tüm kontrol nedenleri", None)
        for value in sorted({r.issue or r.reason or r.rule for r in rows} - {""}):
            self.reason_filter.addItem(_display_engine_code(value), value)
        self.reason_filter.setCurrentIndex(max(0, self.reason_filter.findData(reason)))
        self.reason_filter.blockSignals(False)
        current_region = self.region_filter.currentData()
        current_source = self.source_filter.currentData()
        regions = sorted({r.region for r in rows if r.region and r.region != "BILINMEYEN_BOLGE"})
        sources = sorted({Path(r.source).name for r in rows})
        self.region_filter.blockSignals(True)
        self.region_filter.clear()
        self.region_filter.addItem(f"Tüm bölgeler ({len(regions)})", None)
        for region in regions:
            self.region_filter.addItem(region, region)
        index = self.region_filter.findData(current_region)
        self.region_filter.setCurrentIndex(max(0, index))
        self.region_filter.blockSignals(False)
        self.source_filter.blockSignals(True)
        self.source_filter.clear()
        self.source_filter.addItem("Tüm kaynaklar", None)
        for source in sources:
            self.source_filter.addItem(source, source)
        index = self.source_filter.findData(current_source)
        self.source_filter.setCurrentIndex(max(0, index))
        self.source_filter.blockSignals(False)

    def _render_sources(self) -> None:
        self.sources.setRowCount(len(self.view.sources))
        for n, source in enumerate(self.view.sources):
            values = [
                Path(source.path).name,
                source.adapter,
                ", ".join(sorted({r.region for r in source.records})) or "—",
                ", ".join(sorted({r.bank for r in source.records if r.bank})) or "—",
                str(len(source.records)),
                source.error or source.receipt_summary or "—",
                money_text(source.total) if source.adapter == "MANİM Excel" else "—",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(source.path if c == 0 else value)
                self.sources.setItem(n, c, item)

    def _render_reconciliation(self) -> None:
        result = reconcile(self.view, self.summary)
        lines = ["Muhasebe mutabakat özeti", "", f"Kaynak toplamı: {money_text(result.source_total)}"]
        if self.summary:
            for field, label in (
                ("netsis_total", "Muhasebe çıktısı"),
                ("payment_total", "Ödeme onaylandı"),
                ("reference_total", "Referanslı"),
                ("virman_total", "Virman"),
                ("rule_total", "Kural çalıştı"),
                ("review_total", "İncelemede"),
                ("pending_total", "Bekleyen bakiye"),
            ):
                lines.append(f"{label}: {money_text(self.summary.total(field))}")
        lines.extend([
            f"Dağıtılan: {money_text(result.distributed)}",
            f"Fark: {money_text(result.difference)}",
            "",
            result.limitation,
            "Şubeli / normal ayrımı mevcut çıktı toplamında birleşir; ikinci kez toplama eklenmez.",
        ])
        self.reconciliation.setPlainText("\n".join(lines))

    def _render_previous(self) -> None:
        previous = previous_operation(self.history, self._operation_id)
        self.previous.setText(
            "Önceki başarılı karşılaştırılabilir işlem bulunamadı."
            if previous is None
            else (
                f"Önceki başarılı işlem #{previous[0].id}\n"
                f"{previous[0].started_at}\n\n"
                f"{sum(b.record_count for b in previous[1].buckets)} motor kaydı\n"
                f"{money_text(previous[1].manim_total)}\n\n"
                "Aynı firma / MANİM adaptörü. Dönem ve kaynak kapsamı değişebilir."
            )
        )

    # ------------------------------------------------------------ record table
    def _set_filter_mode(self, mode: str) -> None:
        self._filter_mode = mode
        for name, button in (("attention", self.attention_tab), ("ready", self.ready_tab), ("all", self.all_tab)):
            button.setChecked(name == mode)
        self.render_records()

    def render_records(self, *_):
        query = self.search.text().casefold()
        region = self.region_filter.currentData()
        source = self.source_filter.currentData()
        rows = detail_rows(self.view, self.audits)

        def accepted(row) -> bool:
            reason = self.reason_filter.currentData()
            if reason and (row.issue or row.reason or row.rule) != reason:
                return False
            if self._filter_mode == "attention" and row.priority >= 3:
                # Before the engine has emitted decisions, keep source records
                # visible instead of presenting a falsely empty work queue.
                if self.audits:
                    return False
            if self._filter_mode == "ready" and not (row.outcome and row.priority >= 3):
                return False
            if region and row.region != region:
                return False
            if source and Path(row.source).name != source:
                return False
            haystack = f"{row.source} {row.description} {row.outcome} {row.rule} {row.reason} {row.issue} {row.region}".casefold()
            return query in haystack

        self._filtered_rows = tuple(row for row in rows if accepted(row))
        page_size = max(1, getattr(self, "_page_size_value", 50))
        pages = max(1, (len(self._filtered_rows) + page_size - 1) // page_size)
        self._page_index = min(max(0, getattr(self, "_page_index", 0)), pages - 1)
        start = self._page_index * page_size
        end = min(start + page_size, len(self._filtered_rows))
        self._rows = self._filtered_rows[start:end]

        self.records.blockSignals(True)
        self.records.setSortingEnabled(False)
        self.records.setRowCount(len(self._rows))
        source_adapter = {s.path: s.adapter for s in self.view.sources}
        for n, row in enumerate(self._rows):
            status, tone = self._status_for(row)
            check_host = QWidget()
            check_host.setObjectName("recordCheckHost")
            check_layout = QHBoxLayout(check_host)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check = QCheckBox()
            check.setObjectName("recordCheck")
            check.setFocusPolicy(Qt.NoFocus)
            check_layout.addWidget(check, 0, Qt.AlignCenter)
            self.records.setCellWidget(n, 0, check_host)
            marker = QTableWidgetItem()
            marker.setData(Qt.UserRole, n)
            self.records.setItem(n, 0, marker)

            status_cell = QLabel(f"●  {status}")
            status_cell.setObjectName("recordStatusPill")
            status_cell.setProperty("tone", tone)
            status_cell.setAlignment(Qt.AlignCenter)
            status_cell.setMargin(4)
            self.records.setCellWidget(n, 1, status_cell)

            description = row.description.strip() or Path(row.source).stem
            subtitle = row.receipt.strip() or f"Kaynak satırı #{row.row}"
            desc_item = QTableWidgetItem(f"{description}\n{subtitle}")
            desc_item.setToolTip(f"{description}\n{row.source}")
            desc_item.setData(Qt.UserRole, n)
            self.records.setItem(n, 2, desc_item)

            values = [
                row.region if row.region != "BILINMEYEN_BOLGE" else "Bilinmiyor",
                source_adapter.get(row.source, "Excel"),
                _amount_text(row.amount),
                _display_engine_code(row.issue or row.reason or row.rule) if (row.issue or row.reason or row.rule)
                else ("Planı önizleyin" if not row.outcome else "Hazır"),
                _display_datetime(row.date),
            ]
            for c, value in enumerate(values, start=3):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, n)
                item.setToolTip(value)
                if c == 3:
                    item.setForeground(QColor('#315080'))
                elif c == 5:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    item.setForeground(QColor('#173F8A'))
                    font = item.font(); font.setBold(True); item.setFont(font)
                elif c == 6:
                    item.setForeground(QColor('#315080' if tone == 'success' else '#9B6200' if tone == 'warning' else '#C11E39' if tone == 'critical' else '#536987'))
                self.records.setItem(n, c, item)
            self.records.setRowHeight(n, 34)
        self.records.setSortingEnabled(False)
        self.records.blockSignals(False)

        filtered = len(self._filtered_rows)
        total = len(rows)
        if filtered:
            self.record_range.setText(f"{start + 1}–{end} / {filtered} kayıt")
        else:
            self.record_range.setText(f"0 / {total} kayıt")
        self.page_number.setText(f"{self._page_index + 1} / {pages}")
        self.page_prev.setEnabled(self._page_index > 0)
        self.page_next.setEnabled(self._page_index < pages - 1)

        if self._rows:
            self.records.selectRow(0)
            self.show_detail()
        else:
            self._render_empty_inspector()

    @staticmethod
    def _status_for(row) -> tuple[str, str]:
        if row.issue:
            return "Eksik bilgi", "critical"
        if row.outcome == "SKIPPED":
            return "Geçersiz", "critical"
        if row.outcome == "REVIEW":
            return "İnceleme", "warning"
        if row.outcome == "MANUAL_HAVALE":
            return "Manuel karar", "warning"
        if row.outcome in {"REFERANSLI", "ODEME_ONAYLANDI"}:
            return "Yönlendirildi", "success"
        if row.outcome:
            return "Hazır", "success"
        if not row.receipt:
            return "İnceleme", "warning"
        return "Önizleme", "info"

    def _render_empty_inspector(self) -> None:
        self.inspector_count.setText("Kayıt seçilmedi")
        self.inspector_status.hide()
        self.record_summary.clear()
        self.matching_button.setEnabled(False)
        self.evidence_scroll.hide()
        self.inspector.show()
        self.inspector.setStyleSheet("QTextBrowser { background:#FFFFFF; border:none; color:#172033; font-family:'Segoe UI'; }")
        self.inspector.setHtml(
            "<style>" + self._inspector_css() + "</style>"
            "<div style='font-size:12px;color:#64748B'>"
            "<p>İncelemek için tablodan bir kayıt seçin.</p>"
            "<p>Kaynak, eşleştirme nedeni ve hedef kayıt burada görünür.</p></div>"
        )

    def show_detail(self):
        selected = self.records.selectedItems()
        if not selected:
            self._render_empty_inspector()
            return
        index = next((item.data(Qt.UserRole) for item in selected if item.data(Qt.UserRole) is not None), None)
        if index is None or not (0 <= int(index) < len(self._rows)):
            return
        row = self._rows[int(index)]
        self.matching_button.setEnabled(True)
        self.inspector_count.setText(
            f"{min(self._page_index * self._page_size_value + int(index) + 1, len(self._filtered_rows)):,} / "
            f"{len(self._filtered_rows):,} kayıt".replace(",", ".")
        )
        status, tone = self._status_for(row)
        source_name = Path(row.source).name
        title = (row.description.strip() or source_name)
        compact_title = title if len(title) <= 74 else title[:71].rstrip() + "…"
        display_date = _display_datetime(row.date)
        raw_reason = row.issue or row.reason
        raw_rule = row.rule
        reason = _display_engine_code(raw_reason) if raw_reason else "Motor karar ayrıntısı henüz yok."
        rule = _display_engine_code(raw_rule) if raw_rule else "—"
        outcome = {
            "HAVALE": "Gelen havale", "MATCH": "Eşleşti", "MANUAL_HAVALE": "Manuel havale",
            "REVIEW": "İnceleme bekliyor", "SKIPPED": "İncelemede bırakıldı",
            "REFERANSLI": "Referanslı", "ODEME_ONAYLANDI": "Ödeme onaylandı",
            "VIRMAN": "Virman", "SAME_BANK_VIRMAN": "Aynı banka virmanı",
            "KURAL_CALISTI": "Kural uygulandı",
        }.get(row.outcome, "Henüz hesaplanmadı" if not row.outcome else "Motor kararı mevcut")
        receipt = row.receipt or "Boş"
        region = "Bilinmiyor" if row.region == "BILINMEYEN_BOLGE" else row.region
        self.inspector_status.setText(f"●  {status}")
        self.inspector_status.setProperty("tone", tone)
        self.inspector_status.style().unpolish(self.inspector_status)
        self.inspector_status.style().polish(self.inspector_status)
        self.inspector_status.show()
        self.record_summary.setText(
            f"<p style='margin:3px 0;font-size:14px;font-weight:700;line-height:1.12'>{self._escape(compact_title)}</p>"
            "<p style='margin:1px 0;font-size:9px;color:#65758B'>Cari hesap · —</p>"
            f"<p style='margin:5px 0 3px 0;font-size:21px;font-weight:700'>{self._escape(_amount_text(row.amount))}</p>"
            f"<p style='margin:2px 0;font-size:9px;color:#53657D'>{self._escape(region)} · "
            f"{self._escape(row.bank)} · {self._escape(display_date)}</p>"
        )
        self.record_summary.setToolTip(title)
        html = f"""
        <div class='record'>
          <div class='muted'>Seçili kayıt · kaynak satırı {row.row}</div>
          <h3>Neden bu kayıt?</h3>
          <div class='reasonrow'><span class='reasonicon'>✓</span><b>{self._escape(reason)}</b></div>
          <div class='rule'>Kural: {self._escape(rule)}</div>
          <p>Eşleşme güveni: motor sayısal güven puanı sunmuyor.</p>
          <div class='divider'></div>
          <h3>Kaynak</h3>
          <table>
            <tr><td>Dosya</td><td><b>{self._escape(source_name)}</b></td></tr>
            <tr><td>Bölge</td><td><b>{self._escape(region)}</b></td></tr>
            <tr><td>Banka</td><td><b>{self._escape(row.bank or '—')}</b></td></tr>
            <tr><td>Tarih</td><td><b>{self._escape(row.date or '—')}</b></td></tr>
          </table>
          <div class='divider'></div>
          <h3>Hedef kayıt</h3>
          <table>
            <tr><td>Çıktı adaptörü</td><td><b>Netsis Excel</b></td></tr>
            <tr><td>Muhasebe kararı</td><td><b>{self._escape(outcome)}</b></td></tr>
            <tr><td>Tutar</td><td><b>{self._escape(_amount_text(row.amount))}</b></td></tr>
          </table>
        </div>
        """
        tab = self.inspector_tabs.currentIndex()
        self.evidence_scroll.setVisible(tab == 0)
        self.inspector.setVisible(tab != 0)
        for key, value in (("reason", reason), ("rule", rule), ("outcome", outcome),
                           ("source", f"{source_name} · satır {row.row}")):
            self.evidence_values[key].setText(value)

        icon_states = {
            # Missing decision detail is neutral, never a synthetic success.
            "reason": (
                ("×", "critical") if raw_reason and tone == "critical"
                else ("!", "warning") if raw_reason
                else ("•", "neutral")
            ),
            "rule": ("✓", "success") if raw_rule else ("•", "neutral"),
            "outcome": (("×", "critical") if tone == "critical" else ("!", "warning") if tone == "warning" else ("✓", "success") if tone == "success" else ("•", "info")),
            "source": ("✓", "success"),
        }
        for key, (glyph, icon_tone) in icon_states.items():
            icon = self.evidence_icons[key]
            icon.setText(glyph)
            icon.setProperty("tone", icon_tone)
            icon.style().unpolish(icon)
            icon.style().polish(icon)
        for key, value in (("adapter", "Netsis Excel"), ("account", "—"), ("rule", rule), ("amount", _amount_text(row.amount))):
            self.target_values[key].setText(value)
        self.target_values["account"].setToolTip("Mevcut kayıt özeti hedef cari hesap alanını sunmuyor.")
        self.inspector_warning.setText(_display_engine_code(raw_reason) if raw_reason else "")
        self.inspector_warning.setVisible(bool(raw_reason))
        if tab == 1:
            html = (
                f"<h3>Kaynak bilgileri</h3><p>{self._escape(row.source)}</p>"
                f"<p>Satır {row.row} · {self._escape(region)} · {self._escape(row.bank)}</p>"
                f"<p>{self._escape(display_date)} · {self._escape(receipt)}</p>"
                f"<p>{self._escape(title)}</p><h3>{self._escape(_amount_text(row.amount))}</h3>"
            )
        elif tab == 2:
            html = (
                f"<h3>Motor karar izi</h3><p>{self._escape(outcome)}</p>"
                f"<p>Kural: {self._escape(rule)}</p><p>{self._escape(reason)}</p>"
                "<p>Bu görünüm mevcut motor kararını gösterir.</p>"
            )
        elif tab == 3:
            html = "<h3>Notlar</h3><p>Bu kayıt için kayıtlı not sunulmuyor.</p>"
        self.inspector.setStyleSheet("QTextBrowser { background:#FFFFFF; border:none; color:#172033; font-family:'Segoe UI'; }")
        self.inspector.setHtml("<style>" + self._inspector_css() + "</style>" + html)
        self.inspector.setToolTip(row.source)

    def _move_selection(self, delta: int) -> None:
        if not self._rows:
            return
        current = self.records.currentRow()
        target = min(max(0, current + delta), len(self._rows) - 1)
        self.records.selectRow(target)

    @staticmethod
    def _escape(value: object) -> str:
        import html
        return html.escape(str(value))

    @staticmethod
    def _inspector_css() -> str:
        return """
        h1 { font-size:14px; font-weight:650; line-height:1.12; margin:7px 0 2px 0; color:#101828; }
        h3 { font-size:11px; font-weight:750; margin:12px 0 6px 0; color:#172033; }
        .muted { color:#7A8799; font-size:9px; }
        .recordcode { color:#53647D; font-size:9px; margin-bottom:2px; }
        .amount { font-size:20px; font-weight:650; margin:9px 0 1px 0; color:#101828; }
        .sub { color:#46566E; font-size:9px; margin-bottom:7px; }
        .tabs { color:#667085; border-bottom:1px solid #E5EAF1; padding:7px 0; font-size:9px; }
        .tabactive { color:#315BE8; font-weight:700; border-bottom:2px solid #315BE8; }
        .pill { display:inline-block; padding:3px 7px; border-radius:8px; font-size:9px; margin-top:5px; }
        .amber { color:#A46108; background:#FFF1CC; }
        .red { color:#C1152D; background:#FFE4E8; }
        .green { color:#087A4B; background:#DDF7EB; }
        .blue { color:#315BE8; background:#EEF2FF; }
        .reasonrow { background:#F8FAFD; border:1px solid #E5EAF1; padding:7px; border-radius:6px; font-size:9px; color:#172033; }
        .reasonicon { color:#0A9D63; font-size:11px; margin-right:5px; }
        .rule { color:#718096; font-size:8px; margin:4px 0 0 2px; }
        .divider { border-top:1px solid #E8EDF3; margin:9px 0 1px 0; }
        table { width:100%; font-size:11px; border-collapse:collapse; }
        td { padding:5px 3px; color:#65758B; }
        td + td { color:#172033; text-align:right; }
        """
