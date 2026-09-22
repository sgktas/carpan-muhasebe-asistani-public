from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from app.ui.design_system import TOKENS

# Compatibility aliases keep existing pages on the central V1 design tokens.
BRAND_NAVY = TOKENS.brand
BRAND_NAVY_DARK = TOKENS.brand_hover
BRAND_ORANGE = TOKENS.brand
BRAND_ORANGE_DARK = TOKENS.brand_hover
BRAND_ORANGE_SOFT = TOKENS.brand_soft
TEXT_PRIMARY = TOKENS.text_primary
TEXT_SECONDARY = TOKENS.text_secondary
TEXT_MUTED = TOKENS.text_muted
BORDER = TOKENS.border
BORDER_STRONG = TOKENS.border_strong
APP_BACKGROUND = TOKENS.app_background
SURFACE = TOKENS.surface
SIDEBAR_BACKGROUND = TOKENS.sidebar

MAIN_STYLE = f"""
QWidget#mainRoot {{
    background-color: {APP_BACKGROUND};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}
QFrame#workspace {{
    background-color: {APP_BACKGROUND};
}}
QFrame#workspaceHeader {{
    background-color: rgba(255, 255, 255, 0.94);
    border-bottom: 1px solid {BORDER};
}}
QLabel#workspaceHeading {{
    color: {TEXT_PRIMARY};
    font-size: 15px;
    font-weight: 650;
}}
QLabel#workspaceSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}
QLabel#workspaceStatus {{
    background-color: #EFF5F8;
    border: 1px solid #D8E4EB;
    border-radius: 9px;
    color: {BRAND_NAVY};
    font-size: 10px;
    font-weight: 650;
    padding: 5px 9px;
}}
QFrame#sidebar {{
    background-color: {SIDEBAR_BACKGROUND};
    border-right: 1px solid {BORDER};
}}
QFrame#brandArea {{
    background-color: {SURFACE};
    border: none;
}}
QLabel#brandDescriptor {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#navSection {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    padding: 0 10px;
}}
QPushButton.navItem {{
    background-color: transparent;
    color: #405261;
    border: 1px solid transparent;
    border-radius: 9px;
    padding: 11px 12px;
    text-align: left;
    font-size: 13px;
}}
QPushButton#sidebarToggle {{
    background-color: #F3F7F9;
    border: 1px solid #DDE6EC;
    border-radius: 8px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
    padding: 8px 10px;
    text-align: left;
}}
QPushButton#sidebarToggle:hover {{
    background-color: #E9F0F4;
    color: {BRAND_NAVY};
}}
QPushButton.navItem:hover {{
    background-color: #F4F7F9;
    color: {BRAND_NAVY};
}}
QPushButton.navItem[active="true"] {{
    background-color: {BRAND_ORANGE_SOFT};
    color: {BRAND_ORANGE_DARK};
    border: 1px solid #F3C9B3;
    font-weight: 650;
}}
QFrame#userCard {{
    background-color: #F7F9FA;
    border: 1px solid {BORDER};
    border-radius: 10px;
}}
QLabel#userName {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#userStatus {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}
QPushButton#logoutButton {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    text-align: left;
    padding: 0;
}}
QPushButton#logoutButton:hover {{
    color: {BRAND_ORANGE_DARK};
}}
QLabel#pageTitle {{
    font-size: 24px;
    font-weight: 650;
    color: {TEXT_PRIMARY};
}}
QLabel#pageSubtitle {{
    font-size: 13px;
    color: {TEXT_SECONDARY};
}}
QLabel#moduleBadge {{
    background-color: #EAF0F4;
    border: 1px solid #D5E0E8;
    border-radius: 10px;
    color: {BRAND_NAVY};
    font-size: 10px;
    font-weight: 700;
    padding: 6px 10px;
}}
QFrame#surfaceCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#metricCard {{
    background-color: #F7FAFC;
    border: 1px solid #DFE8EE;
    border-radius: 10px;
}}
QLabel#metricValue {{
    color: {BRAND_NAVY};
    font-size: 16px;
    font-weight: 750;
}}
QLabel#metricLabel {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
}}
QFrame#workflowSteps {{
    background-color: #EDF3F6;
    border: 1px solid #D9E4EA;
    border-radius: 13px;
}}
QFrame#workflowStep {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
}}
QFrame#workflowStep[stepState="active"] {{
    background-color: #FFFFFF;
    border-color: #B8CBD8;
}}
QFrame#workflowStep[stepState="complete"] {{
    background-color: #F2FAF5;
    border-color: #C7E6D2;
}}
QFrame#workflowStep[stepState="attention"] {{
    background-color: #FFF8EB;
    border-color: #F0D8A6;
}}
QLabel#workflowNumber {{
    background-color: #D8E3E9;
    color: #456273;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#workflowNumber[stepState="active"] {{ background-color: {BRAND_NAVY}; color: #FFFFFF; }}
QLabel#workflowNumber[stepState="complete"] {{ background-color: #39835A; color: #FFFFFF; }}
QLabel#workflowNumber[stepState="attention"] {{ background-color: #C28222; color: #FFFFFF; }}
QLabel#workflowTitle {{ color: {TEXT_PRIMARY}; font-size: 12px; font-weight: 650; }}
QLabel#workflowSubtitle {{ color: {TEXT_SECONDARY}; font-size: 10px; }}
QLabel#cardTitle {{
    color: {TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 650;
}}
QLabel#cardSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel#statusPill {{
    background-color: #F1F4F6;
    border: 1px solid {BORDER};
    border-radius: 9px;
    color: {TEXT_SECONDARY};
    font-size: 11px;
    padding: 5px 9px;
}}
QLabel#statusPill[ready="true"] {{
    background-color: #EAF7EF;
    border: 1px solid #BFE3CB;
    color: #287244;
}}
QFrame#dropArea {{
    background-color: #FBFCFD;
    border: 2px dashed {BORDER_STRONG};
    border-radius: 12px;
}}
QFrame#dropArea:hover {{
    background-color: #F8FAFB;
    border-color: #AEBCC8;
}}
QFrame#dropArea[hasFiles="true"] {{
    background-color: #FFFBF8;
    border: 2px solid {BRAND_ORANGE};
}}
QLabel#dropTitle {{
    color: {TEXT_PRIMARY};
    font-size: 15px;
    font-weight: 650;
}}
QLabel#dropDetail {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QListWidget#fileList {{
    background-color: transparent;
    border: none;
    outline: none;
    color: #405261;
    font-size: 12px;
}}
QListWidget#fileList::item {{
    background-color: #FFFFFF;
    border: 1px solid #E7ECEF;
    border-radius: 7px;
    padding: 7px 9px;
    margin: 2px 0;
}}
QListWidget#fileList::item:selected {{
    background-color: {BRAND_ORANGE_SOFT};
    border-color: #F1C5AE;
    color: {TEXT_PRIMARY};
}}
QPushButton#primary {{
    background-color: {BRAND_NAVY};
    color: #FFFFFF;
    border: 1px solid {BRAND_NAVY};
    border-radius: 9px;
    padding: 11px 20px;
    font-weight: 650;
    min-width: 118px;
}}
QPushButton#primary:hover:!disabled {{
    background-color: {BRAND_NAVY_DARK};
    border-color: {BRAND_NAVY_DARK};
}}
QPushButton#primary:pressed:!disabled {{
    background-color: #102B3D;
}}
QPushButton#primary:disabled {{
    background-color: #DCE3E8;
    border-color: #DCE3E8;
    color: #929EA8;
}}
QPushButton#secondary {{
    background-color: #FFFFFF;
    color: {BRAND_NAVY};
    border: 1px solid #C7D3DC;
    border-radius: 9px;
    padding: 9px 14px;
    font-weight: 600;
}}
QPushButton#secondary:hover {{
    background-color: #F3F7F9;
    border-color: #A8BAC7;
}}
QPushButton#ghost {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 8px 10px;
}}
QPushButton#ghost:hover {{
    background-color: #F3F5F7;
    color: {BRAND_ORANGE_DARK};
}}
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: #E8EDF1;
    height: 8px;
}}
QProgressBar::chunk {{
    background-color: {BRAND_ORANGE};
    border-radius: 4px;
}}
QTextEdit#log {{
    background-color: #FBFCFD;
    border: 1px solid #E3E8EC;
    border-radius: 10px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    color: #465563;
    padding: 10px;
    selection-background-color: #DCE8F0;
}}
QFrame#placeholderCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#placeholderTitle {{
    color: {TEXT_PRIMARY};
    font-size: 17px;
    font-weight: 650;
}}
QLabel#placeholderText {{
    color: {TEXT_SECONDARY};
    font-size: 13px;
}}
QLabel#comingSoonBadge {{
    background-color: {BRAND_ORANGE_SOFT};
    border: 1px solid #F2C9B4;
    border-radius: 9px;
    color: {BRAND_ORANGE_DARK};
    font-size: 10px;
    font-weight: 700;
    padding: 5px 9px;
}}

QFrame#miniInfoCard {{
    background-color: #F8FAFB;
    border: 1px solid #E4E9ED;
    border-radius: 10px;
}}
QLabel#miniInfoTitle {{
    color: #17212B;
    font-size: 12px;
    font-weight: 650;
}}
QLabel#miniInfoText {{
    color: #667584;
    font-size: 11px;
}}
QFrame#settingsRow {{
    background-color: #FBFCFD;
    border: 1px solid #E3E8EC;
    border-radius: 10px;
}}
QTableWidget#historyTable {{
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFB;
    border: 1px solid #E3E8EC;
    border-radius: 10px;
    gridline-color: #E7ECEF;
    selection-background-color: #FFF1E8;
    selection-color: #17212B;
}}
QTableWidget#historyTable::item {{
    padding: 7px;
}}
QHeaderView::section {{
    background-color: #F3F6F8;
    color: #405261;
    border: none;
    border-right: 1px solid #DDE4EA;
    border-bottom: 1px solid #DDE4EA;
    padding: 8px;
    font-weight: 650;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #C8D1D8;
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #AEBAC3;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

# Shared right-hand operation surfaces; navigation and approved files untouched.
MAIN_STYLE += """
QPushButton#disclosureToggle { background: #EAF0F4; color: #214866; border: 1px solid #D6E1E8; border-radius: 9px; padding: 10px 14px; text-align: left; font-weight: 600; }
QPushButton#disclosureToggle:hover { background: #DFEAF1; }
QPushButton:focus { border: 2px solid #CF642D; }
QPushButton#secondary:disabled { color: #8996A0; border-color: #DFE5E9; background: #F3F6F8; }
QFrame#planHero { background: #17364D; border-radius: 12px; }
QLabel#planHeroTitle { color: #FFFFFF; font-size: 19px; font-weight: 650; }
QLabel#planHeroSubtitle { color: #CDDFEB; font-size: 12px; }
QFrame#planMetric { background: #F7FAFC; border: 1px solid #DEE7EE; border-radius: 10px; }
QLabel#planMetricValue { color: #17364D; font-size: 22px; font-weight: 650; }
QLabel#planNotice { background: #EDF7F2; color: #245B47; border: 1px solid #D0E8DC; border-radius: 9px; padding: 12px; }
QLabel#planNotice[attention="true"] { background: #FFF7E9; color: #815419; border-color: #F0DEB9; }
QLabel#activityEmpty { color: #667584; padding: 12px; background: #F7FAFC; border-radius: 8px; }
QTableView#activityTable, QTableWidget#planTable {
    background: #FFFFFF; alternate-background-color: #F7FAFC;
    border: 1px solid #E1E8EE; border-radius: 8px; color: #273F50;
    selection-background-color: #E4EFF7; selection-color: #17364D;
    font-family: "Segoe UI"; font-size: 12px;
}
QTableView#activityTable::item, QTableWidget#planTable::item { padding: 8px; border: none; }
QLineEdit { padding: 8px 10px; border: 1px solid #CFDBE4; border-radius: 7px; background: #FFFFFF; color: #273F50; }
QLineEdit:focus { border-color: #356180; }
QComboBox { padding: 7px 9px; border: 1px solid #CFDBE4; border-radius: 7px; background: #FFFFFF; color: #273F50; }
QTabWidget::pane { border: 1px solid #E1E8EE; border-radius: 8px; background: #FFFFFF; }
QTabBar::tab { padding: 10px 16px; color: #617484; background: #F3F6F8; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #17364D; background: #FFFFFF; border-bottom: 2px solid #CF642D; font-weight: 600; }
"""

# Phase 1 shell overrides. Existing working pages retain their object names;
# their visual language is brought forward through tokens rather than rewrites.
MAIN_STYLE += f"""
QWidget#mainRoot {{ background:{TOKENS.app_background}; color:{TOKENS.text_primary}; }}
QFrame#workspace {{ background:{TOKENS.app_background}; }}
QFrame#workspaceHeader {{ background:{TOKENS.surface}; border-bottom:1px solid {TOKENS.border}; }}
QLabel#workspaceHeading {{ color:{TOKENS.text_primary}; font-size:15px; font-weight:650; }}
QLabel#workspaceSubtitle {{ color:{TOKENS.text_secondary}; font-size:11px; }}
QLabel#workspaceStatus {{ background:{TOKENS.surface_secondary}; border:1px solid {TOKENS.border}; color:{TOKENS.text_secondary}; border-radius:{TOKENS.radius_small}px; padding:4px 8px; }}
QFrame#sidebar {{ background:{TOKENS.sidebar}; border-right:1px solid {TOKENS.sidebar_hover}; }}
QFrame#brandArea {{ background:#F7FAFF; border:1px solid #2C4260; border-radius:{TOKENS.radius_panel}px; }}
QLabel#brandDescriptor {{ color:#607087; }}
QLabel#navSection {{ color:#A8B5C8; }}
QPushButton.navItem {{ color:#D5DDEA; border:1px solid transparent; border-radius:{TOKENS.radius_control}px; padding:7px 10px; min-height:30px; text-align:left; }}
QPushButton.navItem:hover {{ background:{TOKENS.sidebar_hover}; color:#FFFFFF; }}
QPushButton.navItem[active="true"] {{ background:{TOKENS.sidebar_selected}; color:#FFFFFF; border-color:#36558A; font-weight:650; }}
QFrame#sidebarItem {{ background:transparent; border:none; }}
QScrollArea#sidebarNavigationScroll {{ background:transparent; border:none; }}
QWidget#sidebarNavigationContent {{ background:transparent; }}
QScrollArea#sidebarNavigationScroll QScrollBar:vertical {{
    background:transparent;
    width:6px;
    margin:2px 0;
}}
QScrollArea#sidebarNavigationScroll QScrollBar::handle:vertical {{
    background:#465971;
    border-radius:3px;
    min-height:32px;
}}
QScrollArea#sidebarNavigationScroll QScrollBar::handle:vertical:hover {{ background:#60738B; }}
QScrollArea#sidebarNavigationScroll QScrollBar::add-line:vertical,
QScrollArea#sidebarNavigationScroll QScrollBar::sub-line:vertical {{ height:0; }}
QScrollArea#sidebarNavigationScroll QScrollBar::add-page:vertical,
QScrollArea#sidebarNavigationScroll QScrollBar::sub-page:vertical {{ background:transparent; }}
QPushButton#sidebarToggle {{ background:transparent; border:1px solid #33465F; color:#C6D1E0; border-radius:{TOKENS.radius_small}px; }}
QPushButton#sidebarToggle:hover {{ background:{TOKENS.sidebar_hover}; color:#FFFFFF; }}
QFrame#userCard {{ background:{TOKENS.sidebar_hover}; border:1px solid #30445D; border-radius:{TOKENS.radius_panel}px; }}
QLabel#userName {{ color:#FFFFFF; }} QLabel#userStatus {{ color:#B7C4D4; }}
QPushButton#logoutButton {{ color:#B7C4D4; }} QPushButton#logoutButton:hover {{ color:#FFFFFF; }}
QFrame#surfaceCard, QFrame#placeholderCard {{ border-radius:{TOKENS.radius_panel}px; border-color:{TOKENS.border}; }}
QFrame#toolRow {{ background:{TOKENS.surface}; border:1px solid {TOKENS.border}; border-radius:{TOKENS.radius_panel}px; }}
QLabel#automationNotice {{ background:{TOKENS.info_soft}; border:1px solid #CFE0FF; color:{TOKENS.text_secondary}; border-radius:{TOKENS.radius_small}px; padding:12px; }}
QLabel#sectionTitle {{ color:{TOKENS.text_primary}; font-size:15px; font-weight:650; }}
QLabel#sectionSubtitle, QLabel#cardSubtitle {{ color:{TOKENS.text_secondary}; font-size:12px; }}
QLabel#panelTitle {{ color:{TOKENS.text_primary}; font-size:13px; font-weight:650; }}
QFrame#emptyState {{ background:{TOKENS.surface}; border:1px solid {TOKENS.border}; border-radius:{TOKENS.radius_panel}px; }}
QLabel#emptyStateTitle {{ color:{TOKENS.text_primary}; font-size:17px; font-weight:650; }}
QLabel#emptyStateDetail {{ color:{TOKENS.text_secondary}; font-size:13px; }}
QPushButton#primary {{ background:{TOKENS.brand}; border-color:{TOKENS.brand}; border-radius:{TOKENS.radius_control}px; }}
QPushButton#primary:hover:!disabled {{ background:{TOKENS.brand_hover}; border-color:{TOKENS.brand_hover}; }}
QPushButton#secondary {{ color:{TOKENS.brand}; border-color:{TOKENS.border_strong}; border-radius:{TOKENS.radius_control}px; }}
QPushButton#secondary:hover {{ background:{TOKENS.brand_soft}; border-color:{TOKENS.brand}; }}
QPushButton#danger {{ background:{TOKENS.critical}; color:#FFFFFF; border:1px solid {TOKENS.critical}; border-radius:{TOKENS.radius_control}px; padding:9px 14px; font-weight:600; }}
QPushButton#iconButton {{ background:transparent; color:{TOKENS.text_secondary}; border:1px solid transparent; border-radius:{TOKENS.radius_small}px; padding:6px; }}
QPushButton:focus {{ outline:none; border:2px solid {TOKENS.brand}; }}
QTableWidget#historyTable {{ selection-background-color:{TOKENS.brand_soft}; selection-color:{TOKENS.text_primary}; border-radius:{TOKENS.radius_control}px; }}
QHeaderView::section {{ background:{TOKENS.surface_secondary}; color:{TOKENS.text_secondary}; border-color:{TOKENS.border}; }}
"""

# Phase 1B: one visual language for the shell and hosted legacy widgets.
MAIN_STYLE += f"""
QWidget {{ font-family:"{TOKENS.font_family}"; font-size:{TOKENS.body_size}px; color:{TOKENS.text_primary}; }}
QFrame#workspace, QStackedWidget, QScrollArea {{ background:{TOKENS.app_background}; border:none; }}
QWidget#pageCanvas {{ background:{TOKENS.app_background}; }}
QFrame#workspaceHeader {{ background:{TOKENS.surface}; border-bottom:1px solid {TOKENS.border}; }}
QLabel#workspaceHeading {{ font-size:14px; font-weight:600; }}
QLabel#workspaceSubtitle {{ font-size:11px; color:{TOKENS.text_secondary}; }}
QLineEdit#globalSearch {{ background:{TOKENS.surface_secondary}; border:1px solid {TOKENS.border}; border-radius:7px; padding:9px 12px; color:{TOKENS.text_muted}; font-size:12px; }}
QLabel#topbarCompany {{ font-size:12px; font-weight:600; padding:0 8px; }}
QLabel#topbarAvatar {{ color:{TOKENS.brand}; background:{TOKENS.brand_soft}; border-radius:16px; font-size:14px; font-weight:600; }}
QFrame#brandArea {{ background:transparent; border:none; border-radius:0; }}
QLabel#brandDescriptor {{ color:#A0B0C4; font-size:10px; font-weight:400; letter-spacing:0; }}
QLabel#navSection {{ color:#8596AE; font-size:10px; font-weight:600; padding:7px 8px 2px 8px; }}
QPushButton.navItem {{ background:transparent; color:#D4DEEB; font-size:12px; border:none; border-radius:6px; padding:4px 6px; min-height:26px; text-align:left; }}
QPushButton.navItem:hover {{ background:#1D2E46; color:#FFFFFF; }}
QPushButton.navItem[active="true"] {{ background:#243A60; color:#FFFFFF; border:none; font-weight:600; }}
QPushButton#sidebarToggle {{ background:transparent; border:none; color:#96A8C0; padding:4px 8px; font-size:11px; }}
QFrame#userCard {{ background:transparent; border:none; border-top:1px solid #2B3B52; border-radius:0; }}
QLabel#userName {{ color:#EDF2FA; font-size:12px; font-weight:600; }}
QLabel#userStatus {{ color:#96A8C0; font-size:11px; }}
QPushButton#logoutButton {{ background:transparent; border:none; padding:2px 0; color:#AABAD0; font-size:11px; }}
QLabel#pageTitle {{ font-size:{TOKENS.page_title_size}px; font-weight:600; color:{TOKENS.text_primary}; }}
QLabel#pageSubtitle, QLabel#cardSubtitle {{ font-size:{TOKENS.body_size}px; color:{TOKENS.text_secondary}; }}
QLabel#sectionTitle {{ font-size:{TOKENS.section_title_size}px; font-weight:600; }}
QLabel#panelTitle, QLabel#cardTitle {{ font-size:{TOKENS.panel_title_size}px; font-weight:600; }}
QFrame#metricTile, QFrame#metricCard {{ background:{TOKENS.surface}; border:1px solid {TOKENS.border}; border-radius:10px; }}
QLabel#metricValue {{ color:{TOKENS.text_primary}; font-size:{TOKENS.financial_value_size}px; font-weight:600; }}
QLabel#metricLabel {{ color:{TOKENS.text_secondary}; font-size:{TOKENS.metadata_size}px; }}
QPushButton {{ background:{TOKENS.surface}; color:{TOKENS.text_primary}; border:1px solid {TOKENS.border}; border-radius:7px; padding:8px 12px; font-size:13px; }}
QPushButton:hover {{ background:{TOKENS.surface_secondary}; border-color:{TOKENS.border_strong}; }}
QPushButton:disabled {{ color:{TOKENS.text_muted}; background:{TOKENS.surface_secondary}; border-color:{TOKENS.border}; }}
QPushButton#primary {{ background:{TOKENS.brand}; color:#FFFFFF; border:1px solid {TOKENS.brand}; }}
QPushButton#primary:hover:!disabled {{ background:{TOKENS.brand_hover}; }}
QPushButton#secondary {{ background:{TOKENS.surface}; color:{TOKENS.brand}; border:1px solid {TOKENS.border}; }}
QPushButton#danger {{ background:{TOKENS.critical}; color:#FFFFFF; border:1px solid {TOKENS.critical}; }}
QTabWidget::pane {{ background:{TOKENS.app_background}; border:none; border-top:1px solid {TOKENS.border}; }}
QTabBar::tab {{ background:transparent; color:{TOKENS.text_secondary}; padding:10px 20px; border:none; border-bottom:2px solid transparent; }}
QTabBar::tab:selected {{ color:{TOKENS.brand}; background:{TOKENS.surface}; border-bottom:2px solid {TOKENS.brand}; }}
QFrame#surfaceCard, QFrame#toolRow, QFrame#emptyState {{ background:{TOKENS.surface}; border:1px solid {TOKENS.border}; border-radius:10px; }}
QFrame#workflowSteps {{ background:#EEF2F6; border:1px solid {TOKENS.border}; border-radius:8px; }}
QLabel#automationNotice {{ background:#EDF2F8; color:#52637A; border:none; border-radius:8px; padding:14px 16px; font-size:12px; }}
QLabel#moduleBadge {{ background:{TOKENS.brand_soft}; color:{TOKENS.brand}; border:none; border-radius:5px; padding:4px 8px; font-size:10px; }}
QLabel#emptyStateTitle {{ font-size:18px; font-weight:600; }}
QLabel#emptyStateDetail {{ font-size:13px; color:{TOKENS.text_secondary}; }}
"""

LOGIN_STYLE = f"""
QWidget#loginRoot {{
    background-color: {APP_BACKGROUND};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
    color: {TEXT_PRIMARY};
}}
QFrame#loginCard {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}
QFrame#accentLine {{
    background-color: {BRAND_ORANGE};
    border: none;
    border-radius: 2px;
}}
QLabel#loginEyebrow {{
    color: {TEXT_MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#loginTitle {{
    color: {TEXT_PRIMARY};
    font-size: 21px;
    font-weight: 650;
}}
QLabel#loginSubtitle {{
    color: {TEXT_SECONDARY};
    font-size: 12px;
}}
QLabel.fieldLabel {{
    color: #405261;
    font-size: 12px;
    font-weight: 600;
}}
QLineEdit, QComboBox {{
    background-color: #FBFCFD;
    border: 1px solid #D6DEE4;
    border-radius: 9px;
    padding: 10px 12px;
    font-size: 13px;
    color: {TEXT_PRIMARY};
}}
QLineEdit:hover, QComboBox:hover {{
    border-color: #BECAD3;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {BRAND_NAVY};
    background-color: #FFFFFF;
}}
QPushButton#loginButton {{
    background-color: {BRAND_NAVY};
    color: #FFFFFF;
    border: none;
    border-radius: 9px;
    font-weight: 650;
    font-size: 14px;
    padding: 12px;
}}
QPushButton#loginButton:hover {{
    background-color: {BRAND_NAVY_DARK};
}}
QLabel#versionLabel {{
    color: {TEXT_MUTED};
    font-size: 10px;
}}
QLabel#loginError {{
    color: #B42318;
    background-color: #FEF3F2;
    border: 1px solid #FECDCA;
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 11px;
}}
"""


def crisp_pixmap(widget: QWidget, path: Path, target_width: int) -> QPixmap:
    """Return a high-DPI-aware pixmap without changing the original asset."""
    ratio = widget.devicePixelRatioF() or 1.0
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaledToWidth(
        max(1, int(target_width * ratio)),
        Qt.SmoothTransformation,
    )
    scaled.setDevicePixelRatio(ratio)
    return scaled


def asset_icon(assets_dir: Path, name: str, active: bool = False) -> QIcon:
    state = "active" if active else "default"
    path = assets_dir / "icons" / f"{name}-{state}.png"
    return QIcon(str(path)) if path.is_file() else QIcon()


def sidebar_asset_icon(assets_dir: Path, name: str, active: bool = False) -> QIcon:
    """Keep existing icon shapes, with legible contrast on the dark shell."""
    pixmap = asset_icon(assets_dir, name).pixmap(40, 40)
    if pixmap.isNull():
        return QIcon()
    painter = QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor('#FFFFFF' if active else '#CBD5E1'))
    painter.end()
    return QIcon(pixmap)

# Phase 2: approved Muhasebe Otomasyon Merkezi visual parity.
MAIN_STYLE += f"""
/* --- Shell parity with the approved finance workspace mockup --- */
QFrame#sidebar {{ background:#142033; border-right:1px solid #23344D; }}
QFrame#brandArea {{ background:transparent; border:none; }}
QLabel#brandDescriptor {{ color:#9EB0C8; font-size:10px; }}
QFrame#workspaceHeader {{ background:#FFFFFF; border-bottom:1px solid #E2E7EE; }}
QLineEdit#globalSearch {{ min-height:18px; background:#F8FAFD; border:1px solid #DCE3EC; border-radius:7px; }}

/* --- Accounting page canvas --- */
QWidget#accountingWorkspace,
QWidget#automationNewWorkPage,
QWidget#automationSourcesPage,
QStackedWidget#accountingStack {{
    background:#F7F9FC;
}}
QLabel#automationTitleIcon {{
    color:#315BE8;
    font-size:24px;
    font-weight:700;
}}
QLabel#automationPageTitle {{
    color:#101828;
    font-size:23px;
    font-weight:700;
}}
QLabel#automationPageSubtitle {{
    color:#52627A;
    font-size:12px;
}}
QFrame#automationSummaryRail,
QFrame#automationStepRail,
QFrame#automationDecisionRail {{
    background:#FFFFFF;
    border:1px solid #DDE4EE;
    border-radius:7px;
}}
QFrame#automationStatBlock {{
    background:transparent;
    border:none;
}}
QLabel#automationStatValue {{
    color:#101828;
    font-size:14px;
    font-weight:700;
}}
QLabel#automationStatDetail {{
    color:#52709E;
    font-size:10px;
}}
QFrame#automationRailDivider {{
    background:#E4E9F1;
    border:none;
}}
QPushButton#automationAddSource {{
    background:#FFFFFF;
    color:#2457F5;
    border:1px solid #6E8AFF;
    border-radius:6px;
    padding:8px 13px;
    font-weight:700;
}}
QPushButton#automationAddSource:hover {{
    background:#F2F5FF;
    border-color:#315BE8;
}}
QPushButton#automationClearSource {{
    background:transparent;
    color:#667085;
    border:none;
    padding:8px 9px;
}}
QPushButton#automationClearSource:hover {{ color:#315BE8; background:#F4F6FA; }}

QFrame#automationStep {{ background:transparent; border:none; }}
QLabel#automationStepNumber {{
    background:#EDF1F7;
    color:#667085;
    border-radius:12px;
    font-size:10px;
    font-weight:700;
}}
QLabel#automationStepNumber[stepState="active"] {{ background:#315BE8; color:#FFFFFF; }}
QLabel#automationStepNumber[stepState="complete"] {{ background:#315BE8; color:#FFFFFF; }}
QLabel#automationStepTitle {{ color:#667085; font-size:10px; }}
QLabel#automationStepTitle[stepState="active"] {{ color:#315BE8; font-weight:700; }}
QLabel#automationStepTitle[stepState="complete"] {{ color:#344054; font-weight:600; }}
QFrame#automationStepConnector {{ background:#DDE4EE; border:none; min-width:10px; }}
QLabel#automationStepNote {{ color:#71809A; font-size:9px; }}

QFrame#decisionLegend {{ background:transparent; border:none; }}
QLabel#decisionLegendText {{ color:#344054; font-size:10px; }}
QLabel#decisionDot[tone="success"] {{ color:#14A66C; }}
QLabel#decisionDot[tone="warning"] {{ color:#F4A915; }}
QLabel#decisionDot[tone="manual"] {{ color:#F08C16; }}
QLabel#decisionDot[tone="critical"] {{ color:#E6284E; }}
QLabel#decisionTotal {{ color:#233B66; font-size:10px; font-weight:700; }}
QFrame#decisionBar {{ background:#E9EEF5; border:none; border-radius:4px; min-height:8px; max-height:8px; }}
QFrame#decisionBar[empty="true"] {{ background:#E9EEF5; }}
QFrame#decisionBarSegment {{ border:none; min-height:8px; max-height:8px; }}
QFrame#decisionBarSegment[tone="success"] {{ background:#16B878; }}
QFrame#decisionBarSegment[tone="warning"] {{ background:#F7B218; }}
QFrame#decisionBarSegment[tone="manual"] {{ background:#F18A16; }}
QFrame#decisionBarSegment[tone="critical"] {{ background:#E7284E; }}

QLabel#automationSectionTitle {{ color:#101828; font-size:17px; font-weight:700; }}
QPushButton#automationViewTab {{
    background:transparent;
    color:#52627A;
    border:none;
    border-bottom:2px solid transparent;
    border-radius:0;
    padding:5px 7px;
    font-size:11px;
}}
QPushButton#automationViewTab:checked {{
    color:#2457F5;
    border-bottom:2px solid #315BE8;
    font-weight:700;
}}
QLineEdit#automationSearch,
QComboBox#automationFilter {{
    background:#FFFFFF;
    color:#344054;
    border:1px solid #CED7E4;
    border-radius:6px;
    padding:7px 10px;
    min-height:20px;
    font-size:11px;
}}
QLineEdit#automationSearch:focus,
QComboBox#automationFilter:focus {{ border:1px solid #6F8DFF; }}
QPushButton#automationToolbarButton {{
    background:#FFFFFF;
    color:#344054;
    border:1px solid #CED7E4;
    border-radius:6px;
    padding:7px 11px;
    font-size:11px;
}}

QSplitter#automationMainSplit {{ background:#F7F9FC; }}
QTableWidget#attentionTable,
QTableWidget#sourceSummaryTable {{
    background:#FFFFFF;
    alternate-background-color:#FFFFFF;
    border:1px solid #D9E1EC;
    border-radius:6px;
    gridline-color:#E3E8F0;
    selection-background-color:#EAF1FF;
    selection-color:#172033;
    outline:none;
}}
QTableWidget#attentionTable::item,
QTableWidget#sourceSummaryTable::item {{
    padding:5px 7px;
    border:none;
}}
QTableWidget#attentionTable::item:selected {{
    background:#EAF1FF;
    color:#172033;
}}
QTableWidget#attentionTable QHeaderView::section,
QTableWidget#sourceSummaryTable QHeaderView::section {{
    background:#F5F7FB;
    color:#344054;
    border:none;
    border-right:1px solid #E1E6EE;
    border-bottom:1px solid #DCE3EC;
    padding:7px 7px;
    font-size:10px;
    font-weight:700;
}}
QLabel#recordStatusPill {{
    border:none;
    border-radius:10px;
    padding:2px 6px;
    font-size:9px;
    font-weight:600;
}}
QLabel#recordStatusPill[tone="warning"] {{ background:#FFF0C7; color:#9A5D00; }}
QLabel#recordStatusPill[tone="critical"] {{ background:#FFE1E6; color:#C1122F; }}
QLabel#recordStatusPill[tone="success"] {{ background:#DFF7EB; color:#0B7B4E; }}
QLabel#recordStatusPill[tone="info"] {{ background:#EEF2FF; color:#315BE8; }}

QFrame#inspectorPanel {{
    background:#FFFFFF;
    border:1px solid #D9E1EC;
    border-radius:6px;
}}
QLabel#inspectorTitle {{ color:#101828; font-size:13px; font-weight:700; }}
QPushButton#inspectorNavButton {{
    background:#FFFFFF;
    border:1px solid #D8E0EA;
    border-radius:5px;
    color:#315BE8;
    padding:0;
}}
QPushButton#inspectorNavButton:hover {{ background:#F1F5FF; }}
QTextBrowser#recordInspector {{
    background:#FFFFFF;
    border:none;
    color:#172033;
    padding:0;
}}
QPushButton#inspectorPrimaryAction {{
    background:#315BE8;
    color:#FFFFFF;
    border:1px solid #315BE8;
    border-radius:5px;
    padding:9px 11px;
    font-weight:700;
}}
QPushButton#inspectorPrimaryAction:hover:!disabled {{ background:#274CCA; }}
QPushButton#inspectorSecondaryAction {{
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #C9D4E5;
    border-radius:5px;
    padding:9px 10px;
}}
QPushButton#inspectorPrimaryAction:disabled,
QPushButton#inspectorSecondaryAction:disabled {{
    background:#EEF1F5;
    color:#98A2B3;
    border-color:#E0E5EC;
}}
QLabel#automationFooterText {{ color:#667085; font-size:9px; }}
QTextBrowser#reconciliationPanel,
QLabel#previousOperationPanel {{
    background:#FFFFFF;
    border:1px solid #DDE4EE;
    border-radius:7px;
    padding:12px;
    color:#344054;
}}
"""

MAIN_STYLE += f"""
QLabel#workspaceContext {{ color:#5D73A3; font-size:11px; }}
QPushButton#topbarTextAction {{
    background:transparent; border:none; color:#304C7A; padding:6px 8px; font-size:11px;
}}
QPushButton#topbarTextAction:hover:!disabled {{ background:#F4F7FB; color:#315BE8; }}
QPushButton#topbarTextAction:disabled {{ color:#536987; background:transparent; }}
QPushButton#topbarIconAction {{
    background:transparent; border:none; color:#304C7A; padding:0; font-size:16px;
}}
QFrame#companyCard {{
    background:#16263B; border:1px solid #334A67; border-radius:7px;
}}
QLabel#companyCardName {{ color:#F4F7FB; font-size:11px; font-weight:700; }}
QLabel#companyCardHint {{ color:#91A4BE; font-size:9px; }}
QFrame#accountingSubnav {{ background:transparent; border-left:1px solid #2D4261; }}
QPushButton#accountingSubnavButton {{
    background:transparent; color:#C8D4E5; border:none; border-radius:5px;
    padding:5px 8px; text-align:left; font-size:10px;
}}
QPushButton#accountingSubnavButton:hover {{ background:#1D2F49; color:#FFFFFF; }}
QPushButton#accountingSubnavButton[active="true"] {{
    background:#315BE8; color:#FFFFFF; font-weight:700;
}}
"""

# Phase 2 visual parity pass: match the approved mockup's proportions rather
# than merely re-skinning the legacy import page.
MAIN_STYLE += """
QFrame#sidebar { background:#111F33; }
QFrame#companyCard { background:#14263D; border:1px solid #314966; border-radius:6px; }
QPushButton.navItem { padding:6px 7px; min-height:28px; border-radius:5px; font-size:11px; }
QPushButton.navItem[active="true"] { background:#203A63; border-color:#203A63; }
QLabel#navSection { font-size:9px; font-weight:600; letter-spacing:.2px; }
QPushButton#accountingSubnavButton { padding:5px 7px; min-height:18px; font-size:10px; }
QFrame#userCard { background:transparent; border:none; border-top:1px solid #273A52; border-radius:0; }

QFrame#workspaceHeader { min-height:44px; max-height:44px; }
QLabel#workspaceHeading { font-size:13px; font-weight:650; }
QLineEdit#globalSearch { min-height:20px; max-height:28px; }

QWidget#automationCanvas { background:#F7F9FC; }
QLabel#automationPageTitle { font-size:24px; }
QLabel#automationPageSubtitle { font-size:11px; }
QLabel#automationHeaderState {
    background:#F2F5FA; color:#667085; border:1px solid #E0E6EF;
    border-radius:5px; padding:4px 8px; font-size:9px; font-weight:600;
}
QLabel#automationHeaderState[state="ready"] { background:#EAF8F1; color:#118357; border-color:#CDEEDD; }
QLabel#automationHeaderState[state="busy"] { background:#EEF2FF; color:#315BE8; border-color:#D9E2FF; }
QLabel#automationHeaderState[state="error"] { background:#FDECEC; color:#C33B3B; border-color:#F5D1D1; }
QFrame#automationSummaryRail { border-radius:6px; }
QFrame#automationStepRail { border-radius:6px; }
QFrame#automationDecisionRail { border-radius:6px; }
QLabel#automationSectionTitle { font-size:16px; }

QFrame#inspectorPanel {
    background:#FFFFFF;
    border:none;
    border-left:1px solid #D9E1EC;
    border-radius:0;
}
QLabel#inspectorTitle { font-size:13px; }
QLabel#inspectorMeta { color:#667085; font-size:10px; }
QPushButton#inspectorPrimaryAction { min-height:34px; }
QPushButton#inspectorSecondaryAction { min-height:34px; }

QTableWidget#attentionTable { border-radius:4px; }
QTableWidget#attentionTable QHeaderView::section { padding:6px 6px; }
QLabel#recordStatusPill { border-radius:9px; }
"""

# Phase 2 V4 — premium parity overrides.  Kept last deliberately so these
# rules win over compatibility styling above without changing legacy pages.
MAIN_STYLE += """
/* ===== Premium shell ===== */
QFrame#sidebar {
    background:#101E32;
    border-right:1px solid #22334B;
}
QFrame#brandArea { padding:0; }
QLabel#brandDescriptor {
    color:#8FA3BE;
    font-size:9px;
    font-weight:500;
    letter-spacing:.8px;
}
QFrame#companyCard {
    background:#12243B;
    border:1px solid #304967;
    border-radius:8px;
}
QFrame#companyCard:hover { border-color:#4B6485; background:#152A45; }
QLabel#companyCardName { color:#F7F9FC; font-size:11px; font-weight:700; }
QLabel#companyCardHint { color:#8FA3BE; font-size:9px; }
QLabel#companyCardChevron { color:#B7C6D8; font-size:12px; font-weight:700; }
QLabel#navSection {
    color:#6F86A5;
    font-size:9px;
    font-weight:700;
    padding:3px 8px 2px 8px;
}
QPushButton.navItem {
    background:transparent;
    color:#D5DFEC;
    border:1px solid transparent;
    border-radius:7px;
    padding:4px 8px;
    min-height:22px;
    text-align:left;
    font-size:11px;
}
QPushButton.navItem:hover { background:#172A44; color:#FFFFFF; }
QPushButton.navItem[active="true"] {
    background:#203A63;
    border-color:#294878;
    color:#FFFFFF;
    font-weight:650;
}
QFrame#accountingSubnav { border-left:1px solid #2B405E; margin-left:7px; }
QPushButton#accountingSubnavButton {
    color:#B7C6D8;
    background:transparent;
    border:none;
    border-radius:6px;
    padding:5px 8px;
    min-height:20px;
    font-size:10px;
}
QPushButton#accountingSubnavButton:hover { background:#182D48; color:#FFFFFF; }
QPushButton#accountingSubnavButton[active="true"] {
    background:#315BE8;
    color:#FFFFFF;
    font-weight:700;
}
QFrame#userCard {
    background:transparent;
    border:none;
    border-top:1px solid #263A55;
    border-radius:0;
}
QLabel#sidebarAvatar {
    background:#315BE8;
    color:#FFFFFF;
    border-radius:16px;
    font-size:11px;
    font-weight:700;
}
QLabel#userName { color:#F7F9FC; font-size:11px; font-weight:650; }
QLabel#userStatus { color:#8FA3BE; font-size:9px; }
QPushButton#logoutButton {
    color:#8196B2;
    background:transparent;
    border:none;
    border-radius:6px;
    padding:0;
    font-size:13px;
}
QPushButton#logoutButton:hover { color:#FFFFFF; background:#1A2D47; }

/* ===== Premium topbar ===== */
QFrame#workspaceHeader {
    background:#FFFFFF;
    border-bottom:1px solid #E5EAF1;
    min-height:34px;
    max-height:34px;
}
QLabel#workspaceHeading { color:#172033; font-size:13px; font-weight:700; }
QLabel#workspaceContext { color:#74839A; font-size:10px; }
QPushButton#topbarTextAction {
    background:transparent;
    border:none;
    border-radius:7px;
    color:#405A83;
    padding:7px 9px;
    font-size:10px;
}
QPushButton#topbarTextAction:hover:!disabled { background:#F5F7FB; color:#315BE8; }
QPushButton#topbarTextAction:disabled { color:#546B8E; background:transparent; }
QLineEdit#globalSearch {
    background:#F8FAFD;
    color:#667085;
    border:1px solid #DCE3ED;
    border-radius:8px;
    min-height:24px;
    max-height:24px;
    padding:0 11px;
    font-size:11px;
}
QFrame#topbarCompanyBox {
    background:#FFFFFF;
    border-left:1px solid #E6EAF0;
    border-radius:0;
}
QLabel#topbarCompany {
    color:#172033;
    font-size:10px;
    font-weight:650;
}
QLabel#topbarAvatar {
    background:#EEF2FF;
    color:#315BE8;
    border-radius:15px;
    font-size:11px;
    font-weight:700;
}
QPushButton#topbarIconAction { color:#496284; font-size:14px; }

/* ===== Accounting workspace canvas ===== */
QWidget#accountingWorkspace,
QWidget#automationNewWorkPage,
QWidget#automationSourcesPage,
QStackedWidget#accountingStack,
QWidget#automationCanvas { background:#F6F8FC; }
QLabel#automationTitleIcon { color:#315BE8; font-size:21px; font-weight:700; }
QLabel#automationPageTitle {
    color:#172033;
    font-size:21px;
    font-weight:700;
}
QLabel#automationPageSubtitle { color:#607089; font-size:11px; }
QLabel#automationHeaderState {
    background:#EEF2FF;
    color:#315BE8;
    border:1px solid #D9E2FF;
    border-radius:7px;
    padding:5px 9px;
    font-size:9px;
    font-weight:650;
}
QLabel#automationHeaderState[state="ready"] { background:#EAF8F1; color:#118357; border-color:#CDEEDD; }
QLabel#automationHeaderState[state="busy"] { background:#EEF2FF; color:#315BE8; border-color:#D9E2FF; }
QLabel#automationHeaderState[state="error"] { background:#FDECEC; color:#C33B3B; border-color:#F5D1D1; }

QFrame#automationSummaryRail,
QFrame#automationDecisionRail {
    background:#FFFFFF;
    border:1px solid #E1E7EF;
    border-radius:10px;
}
QFrame#automationStepRail {
    background:transparent;
    border:none;
    border-radius:0;
}
QFrame#automationStatBlock { background:transparent; border:none; }
QLabel#automationStatIcon {
    color:#315BE8;
    font-size:22px;
    font-weight:700;
}
QLabel#automationStatValue { color:#172033; font-size:14px; font-weight:750; }
QLabel#automationStatDetail { color:#6C7C95; font-size:9px; }
QFrame#automationRailDivider { background:#E5EAF2; }
QPushButton#automationAddSource {
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #6E8AFF;
    border-radius:8px;
    padding:9px 14px;
    min-height:18px;
    font-size:11px;
    font-weight:700;
}
QPushButton#automationAddSource:hover { background:#F2F5FF; border-color:#315BE8; }
QPushButton#automationClearSource {
    background:transparent;
    color:#667085;
    border:none;
    border-radius:7px;
    padding:8px 9px;
    font-size:10px;
}
QPushButton#automationClearSource:hover { background:#F3F5F9; color:#315BE8; }

/* ===== Workflow timeline ===== */
QFrame#automationStep { background:transparent; border:none; }
QLabel#automationStepNumber {
    background:#E9EEF6;
    color:#667085;
    border:none;
    border-radius:12px;
    font-size:10px;
    font-weight:750;
}
QLabel#automationStepNumber[stepState="active"],
QLabel#automationStepNumber[stepState="complete"] { background:#315BE8; color:#FFFFFF; }
QLabel#automationStepTitle { color:#718096; font-size:10px; }
QLabel#automationStepTitle[stepState="active"] { color:#315BE8; font-weight:700; }
QLabel#automationStepTitle[stepState="complete"] { color:#30415D; font-weight:650; }
QFrame#automationStepConnector { background:#D7DFEA; min-height:1px; max-height:1px; }
QLabel#automationStepNote { color:#74839A; font-size:9px; }

/* ===== Decision summary ===== */
QFrame#automationDecisionRail { min-height:62px; }
QFrame#decisionLegend { background:transparent; border:none; }
QLabel#decisionLegendText { color:#344054; font-size:10px; font-weight:600; }
QLabel#decisionDot { font-size:13px; }
QLabel#decisionDot[tone="success"] { color:#12A66B; }
QLabel#decisionDot[tone="warning"] { color:#F0A313; }
QLabel#decisionDot[tone="manual"] { color:#E98213; }
QLabel#decisionDot[tone="critical"] { color:#E72B4E; }
QLabel#decisionTotal { color:#172033; font-size:10px; font-weight:750; }
QFrame#decisionBar {
    background:#E9EEF5;
    border:none;
    border-radius:6px;
    min-height:12px;
    max-height:12px;
}
QFrame#decisionBarSegment { min-height:12px; max-height:12px; border:none; }
QFrame#decisionBarSegment[tone="success"] { background:#14B978; }
QFrame#decisionBarSegment[tone="warning"] { background:#F7B219; }
QFrame#decisionBarSegment[tone="manual"] { background:#EE8A18; }
QFrame#decisionBarSegment[tone="critical"] { background:#E52B4F; }

/* ===== Queue controls ===== */
QLabel#automationSectionTitle { color:#172033; font-size:14px; font-weight:750; }
QPushButton#automationViewTab {
    background:transparent;
    color:#5E6D83;
    border:none;
    border-bottom:2px solid transparent;
    border-radius:0;
    padding:6px 8px;
    font-size:10px;
}
QPushButton#automationViewTab:checked { color:#315BE8; border-bottom:2px solid #315BE8; font-weight:700; }
QLineEdit#automationSearch,
QComboBox#automationFilter {
    background:#FFFFFF;
    color:#344054;
    border:1px solid #D4DCE8;
    border-radius:8px;
    padding:7px 10px;
    min-height:21px;
    font-size:10px;
}
QLineEdit#automationSearch:focus,
QComboBox#automationFilter:focus { border:1px solid #6E8AFF; }
QComboBox#automationFilter::drop-down,
QComboBox#automationPageSize::drop-down { border:none; width:24px; }
QComboBox#automationFilter::down-arrow,
QComboBox#automationPageSize::down-arrow { image:none; width:0; height:0; }
QPushButton#automationToolbarButton,
QPushButton#automationInspectorOpen {
    background:#FFFFFF;
    color:#46566E;
    border:1px solid #D4DCE8;
    border-radius:8px;
    padding:7px 10px;
    min-height:21px;
    font-size:10px;
}
QPushButton#automationToolbarButton:hover:!disabled,
QPushButton#automationInspectorOpen:hover { background:#F6F8FC; border-color:#B8C4D5; color:#315BE8; }

/* ===== Data grid ===== */
QTableWidget#attentionTable,
QTableWidget#sourceSummaryTable {
    background:#FFFFFF;
    alternate-background-color:#FFFFFF;
    border:1px solid #DCE3ED;
    border-radius:9px;
    gridline-color:#E7EBF1;
    selection-background-color:#EEF3FF;
    selection-color:#172033;
    outline:none;
    font-size:10px;
}
QTableWidget#attentionTable::item,
QTableWidget#sourceSummaryTable::item { padding:5px 7px; border:none; }
QTableWidget#attentionTable::item:selected { background:#EEF3FF; color:#172033; }
QTableWidget#attentionTable QHeaderView::section,
QTableWidget#sourceSummaryTable QHeaderView::section {
    background:#F7F9FC;
    color:#344054;
    border:none;
    border-right:1px solid #E6EBF2;
    border-bottom:1px solid #DDE4ED;
    padding:7px 7px;
    font-size:9px;
    font-weight:750;
}
QWidget#recordCheckHost { background:transparent; }
QCheckBox#recordCheck::indicator {
    width:15px;
    height:15px;
    background:#FFFFFF;
    border:1px solid #9AA8BA;
    border-radius:4px;
}
QCheckBox#recordCheck::indicator:hover { border-color:#315BE8; }
QCheckBox#recordCheck::indicator:checked { background:#315BE8; border-color:#315BE8; }
QLabel#recordStatusPill {
    border:none;
    border-radius:10px;
    padding:3px 7px;
    font-size:9px;
    font-weight:650;
}
QLabel#recordStatusPill[tone="warning"] { background:#FFF0C8; color:#9B6200; }
QLabel#recordStatusPill[tone="critical"] { background:#FFE2E7; color:#C11E39; }
QLabel#recordStatusPill[tone="success"] { background:#DFF7EB; color:#0B7B4E; }
QLabel#recordStatusPill[tone="info"] { background:#EEF2FF; color:#315BE8; }
QComboBox#automationPageSize {
    background:#FFFFFF;
    color:#344054;
    border:1px solid #D5DDE8;
    border-radius:7px;
    padding:4px 8px;
    font-size:9px;
}
QPushButton#automationPagerButton {
    background:#FFFFFF;
    color:#53647D;
    border:1px solid #D5DDE8;
    border-radius:7px;
    font-size:11px;
}
QPushButton#automationPagerButton:hover:!disabled { color:#315BE8; border-color:#B7C4D6; }
QPushButton#automationPagerButton:disabled { color:#B6C0CD; background:#F7F8FA; }
QLabel#automationFooterText { color:#718096; font-size:9px; }

/* ===== Inspector ===== */
QFrame#inspectorPanel {
    background:#FFFFFF;
    border:none;
    border-left:1px solid #DCE3ED;
    border-radius:0;
}
QLabel#inspectorTitle { color:#172033; font-size:12px; font-weight:750; }
QLabel#inspectorMeta { color:#718096; font-size:9px; }
QPushButton#inspectorNavButton {
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #D7DFEA;
    border-radius:7px;
    padding:0;
    font-size:12px;
}
QPushButton#inspectorNavButton:hover { background:#F2F5FF; border-color:#B8C6DC; }
QTextBrowser#recordInspector { background:#FFFFFF; border:none; color:#172033; padding:0; }
QPushButton#inspectorPrimaryAction {
    background:#315BE8;
    color:#FFFFFF;
    border:1px solid #315BE8;
    border-radius:7px;
    min-height:36px;
    padding:8px 11px;
    font-size:10px;
    font-weight:700;
}
QPushButton#inspectorSecondaryAction {
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #C8D4E5;
    border-radius:7px;
    min-height:36px;
    padding:8px 10px;
    font-size:10px;
}
QPushButton#inspectorPrimaryAction:disabled,
QPushButton#inspectorSecondaryAction:disabled { background:#EEF1F5; color:#98A2B3; border-color:#E0E5EC; }

/* ===== Scrollbars: remove the classic desktop feel ===== */
QScrollBar:vertical {
    background:transparent;
    width:8px;
    margin:2px 1px 2px 1px;
}
QScrollBar::handle:vertical {
    background:#C4CEDB;
    min-height:30px;
    border-radius:4px;
}
QScrollBar::handle:vertical:hover { background:#AAB7C8; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical { background:transparent; height:0; }
QScrollBar:horizontal {
    background:transparent;
    height:8px;
    margin:1px 2px;
}
QScrollBar::handle:horizontal { background:#C4CEDB; min-width:30px; border-radius:4px; }
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal { background:transparent; width:0; }
"""
MAIN_STYLE += """
QLabel#automationComboArrow {
    background:transparent;
    color:#5F6F86;
    border:none;
    font-size:13px;
    font-weight:700;
}
"""
MAIN_STYLE += """
/* ===== Phase 2 V6 — final approved accounting mockup parity ===== */
QScrollArea#automationCanvasScroll,
QScrollArea#automationCanvasScroll > QWidget > QWidget {
    background:#F6F8FB;
    border:none;
}
QFrame#automationOutputAccess {
    background:#ECF9F2;
    border:1px solid #CBEEDB;
    border-radius:8px;
}
QLabel#automationOutputAccessLabel {
    color:#087A4B;
    font-size:10px;
    font-weight:700;
    padding-left:3px;
}
QPushButton#automationOutputOpen {
    background:#FFFFFF;
    color:#087A4B;
    border:1px solid #B7E4CC;
    border-radius:6px;
    padding:6px 10px;
    font-size:10px;
    font-weight:700;
}
QPushButton#automationOutputOpen:hover { background:#F7FFFA; border-color:#72C99D; }

QFrame#automationMetricStrip {
    background:transparent;
    border:none;
}
QFrame#automationMetricTile {
    background:#FFFFFF;
    border:1px solid #E1E7EF;
    border-radius:9px;
}
QLabel#automationMetricIcon {
    border:none;
    border-radius:15px;
    font-size:17px;
    font-weight:750;
}
QLabel#automationMetricIcon[tone="success"] { background:#E7F8EF; color:#0A9D63; }
QLabel#automationMetricIcon[tone="critical"] { background:#FDEBED; color:#E12D4F; }
QLabel#automationMetricIcon[tone="warning"] { background:#FFF4D8; color:#D99000; }
QLabel#automationMetricIcon[tone="manual"] { background:#FFF0E4; color:#E36E13; }
QLabel#automationMetricIcon[tone="info"] { background:#EEF2FF; color:#315BE8; }
QLabel#automationMetricIcon[tone="neutral"] { background:#F1F4F8; color:#536987; }
QLabel#automationMetricLabel { color:#53657D; font-size:11px; font-weight:500; }
QLabel#automationMetricValue { color:#172033; font-size:16px; font-weight:700; }
QLabel#automationMetricDetail { color:#65758B; font-size:10px; }

QFrame#automationReconciliationStrip {
    background:#FFFFFF;
    border:1px solid #E0E6EF;
    border-radius:9px;
}
QLabel#automationReconIcon { color:#315BE8; font-size:15px; font-weight:700; }
QLabel#automationReconTitle { color:#172033; font-size:12px; font-weight:750; }
QLabel#automationReconHint { color:#718096; font-size:8px; }
QFrame#automationReconCell {
    background:#FFFFFF;
    border:none;
    border-right:1px solid #E9EDF3;
}
QFrame#automationReconCell[tone="success"] {
    background:#ECF9F2;
    border:1px solid #D7F0E2;
    border-radius:7px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF8E8;
    border:1px solid #F5E4B9;
    border-radius:7px;
}
QLabel#automationReconLabel { color:#65758B; font-size:10px; }
QLabel#automationReconValue { color:#172033; font-size:14px; font-weight:700; }

QFrame#automationSourcePanel,
QFrame#automationPreviousPanel {
    background:#FFFFFF;
    border:1px solid #E0E6EF;
    border-radius:9px;
}
QLabel#automationCompactTitle { color:#172033; font-size:11px; font-weight:750; }
QLabel#automationCompactBadge {
    color:#315BE8;
    background:#EEF2FF;
    border-radius:9px;
    padding:3px 7px;
    font-size:8px;
    font-weight:700;
}
QPushButton#automationCompactButton {
    color:#315BE8;
    background:#FFFFFF;
    border:1px solid #D4DCE8;
    border-radius:6px;
    padding:5px 8px;
    font-size:8px;
    font-weight:650;
}
QPushButton#automationCompactButton:hover { background:#F4F6FF; border-color:#9EAFD0; }
QTableWidget#dashboardSourceTable {
    background:#FFFFFF;
    border:1px solid #E6EBF2;
    border-radius:6px;
    gridline-color:#E8EDF3;
    font-size:10px;
}
QTableWidget#dashboardSourceTable::item { padding:3px 5px; border:none; }
QTableWidget#dashboardSourceTable QHeaderView::section {
    background:#F8FAFC;
    color:#4D5E75;
    border:none;
    border-right:1px solid #E7EBF1;
    border-bottom:1px solid #DDE4ED;
    padding:5px;
    font-size:10px;
    font-weight:700;
}
QLabel#automationPreviousDate { color:#315BE8; font-size:10px; font-weight:700; }
QLabel#automationPreviousMetric {
    color:#172033;
    background:#F8FAFC;
    border:1px solid #E7ECF3;
    border-radius:7px;
    padding:7px;
    font-size:10px;
    font-weight:700;
}
QLabel#automationPreviousNote { color:#718096; font-size:8px; }

QLabel#topbarCompanyContext { color:#8795A8; font-size:8px; }
QFrame#topbarCompanyBox {
    background:#FFFFFF;
    border-left:1px solid #E6EBF2;
    border-right:1px solid #E6EBF2;
    border-radius:0;
    padding:0 4px;
}
QLabel#topbarCompany { color:#172033; font-size:10px; font-weight:750; }

/* Inspector refinement: premium contextual drawer, not a fixed legacy pane. */
QFrame#inspectorPanel { background:#FFFFFF; border-left:1px solid #E0E6EF; }
QTextBrowser#recordInspector { background:#FFFFFF; border:none; padding:0 2px; }
QPushButton#inspectorNavButton {
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #D9E1EB;
    border-radius:6px;
}
QPushButton#inspectorNavButton:hover { background:#F3F6FF; border-color:#AAB8D2; }
"""
MAIN_STYLE += """
QPushButton#inspectorOutputAction {
    background:#ECF9F2;
    color:#087A4B;
    border:1px solid #CBEEDB;
    border-radius:7px;
    min-height:30px;
    padding:6px 10px;
    font-size:9px;
    font-weight:700;
}
QPushButton#inspectorOutputAction:hover { background:#F6FFFA; border-color:#82CEA4; }
"""
MAIN_STYLE += """
/* ===== Phase 2 V9 — integrated matching & rules workspace ===== */
QFrame#resolutionQueueHeader,
QFrame#resolutionFooter,
QFrame#resolutionAllocationPanel {
    background:transparent;
    border:none;
}
QListWidget#resolutionQueue {
    background:#FFFFFF;
    border:none;
    border-top:1px solid #E7ECF3;
    color:#334155;
    outline:none;
    padding:6px;
}
QListWidget#resolutionQueue::item {
    min-height:38px;
    padding:7px 9px;
    margin:2px 0;
    border-radius:7px;
}
QListWidget#resolutionQueue::item:hover { background:#F5F7FB; }
QListWidget#resolutionQueue::item:selected {
    background:#EEF2FF;
    color:#234BCF;
    border-left:3px solid #315BE8;
}
QLabel#resolutionRecordTitle {
    color:#172033;
    font-size:20px;
    font-weight:750;
}
QLabel#resolutionReason {
    color:#53657D;
    background:#F8FAFC;
    border:1px solid #E6EBF2;
    border-radius:7px;
    padding:9px 10px;
    font-size:10px;
}
QPushButton#resolutionRoute {
    color:#334155;
    background:#FFFFFF;
    border:1px solid #DCE3EC;
    border-radius:7px;
    padding:7px 10px;
    spacing:5px;
    font-size:12px;
    font-weight:650;
}
QPushButton#resolutionRoute:hover { border-color:#AAB8D2; background:#F8FAFF; }
QPushButton#resolutionRoute:checked {
    color:#234BCF;
    background:#EEF2FF;
    border-color:#9DB0FF;
}
QPushButton#resolutionRoute:focus { border-color:#315BE8; }
QPushButton#resolutionRoute:pressed { background:#DFE7FF; }
QPushButton#resolutionRoute:disabled { color:#667085; background:#F4F6F8; border-color:#E3E7ED; }
QTableWidget#resolutionAllocationTable {
    background:#FFFFFF;
    border:1px solid #E1E7EF;
    border-radius:7px;
    gridline-color:#E8EDF3;
    color:#26364A;
    font-size:13px;
    selection-color:#172033;
    selection-background-color:#EEF2FF;
}
QTableWidget#resolutionAllocationTable::item { padding:5px 7px; }
QTableWidget#resolutionAllocationTable::item:selected { color:#172033; background:#EEF2FF; }
QTableWidget#resolutionAllocationTable::item:hover { color:#172033; background:#F4F6FA; }
QTableWidget#resolutionAllocationTable:disabled { color:#667085; background:#F8F9FB; }
QTableWidget#resolutionAllocationTable QHeaderView::section {
    background:#F8FAFC;
    color:#53657D;
    border:none;
    border-right:1px solid #E7ECF3;
    border-bottom:1px solid #DDE4ED;
    padding:6px;
    font-size:12px;
    font-weight:700;
}
QLabel#resolutionTotal {
    color:#53657D;
    background:#F8FAFC;
    border:1px solid #E6EBF2;
    border-radius:6px;
    padding:7px 9px;
    font-size:12px;
    font-weight:650;
}
QLabel#resolutionTotal[tone="success"] { color:#087A4B; background:#ECF9F2; border-color:#CBEEDB; }
QLabel#resolutionTotal[tone="warning"] { color:#A76400; background:#FFF7E5; border-color:#F4D99B; }
QLabel#resolutionTotal[tone="critical"] { color:#C92A45; background:#FDECEE; border-color:#F6C8D0; }
QFrame#operationActionBar { background:#FFFFFF; border-top:1px solid #E3E7ED; }
QFrame#operationActionBar QLabel { color:#53657D; font-size:12px; }
QTabBar#inspectorTabs::tab { background:#FFFFFF; color:#667085; padding:8px 6px; font-size:11px; border:none; border-bottom:2px solid transparent; }
QTabBar#inspectorTabs::tab:selected { color:#315BE8; border-bottom:2px solid #315BE8; }
QTabBar#inspectorTabs::tab:hover { background:#EEF2FF; }
QLineEdit, QComboBox { selection-background-color:#315BE8; selection-color:#FFFFFF; }
QLineEdit:disabled, QComboBox:disabled { color:#667085; background:#F4F6F8; border-color:#E3E7ED; }
QComboBox QAbstractItemView { color:#172033; background:#FFFFFF; selection-color:#172033; selection-background-color:#EEF2FF; outline:none; }
QPushButton:focus { border:1px solid #315BE8; }
QPushButton:disabled { color:#667085; background:#F4F6F8; border-color:#E3E7ED; }
"""
MAIN_STYLE += """
/* Final visual parity: scoped accounting workstation, not legacy forms. */
QLabel#workspaceHeading { color:#65758B; font-size:11px; font-weight:500; }
QLabel#automationPageTitle { font-size:23px; font-weight:700; }
QLabel#automationPageSubtitle { font-size:13px; color:#405783; }
QLabel#automationSectionTitle, QLabel#automationCompactTitle,
QLabel#automationReconTitle { font-size:13px; font-weight:700; }
QLabel#automationStatDetail { font-size:10px; }
QLabel#automationStepTitle { font-size:11px; }
QFrame#automationStepRail { background:#FFFFFF; border-radius:6px; }
QFrame#automationMetricStrip { background:#FFFFFF; border:1px solid #E7ECF3; border-radius:7px; }
QFrame#automationMetricTile { background:#F7F9FC; border:none; border-radius:6px; }
QLabel#automationMetricIcon { border-radius:10px; font-size:17px; }
QProgressBar#metricProgress { border:none; border-radius:3px; background:#E7ECF3; }
QProgressBar#metricProgress::chunk { border-radius:3px; background:#315BE8; }
QProgressBar#metricProgress[tone="success"]::chunk { background:#13A776; }
QProgressBar#metricProgress[tone="warning"]::chunk { background:#EAAA16; }
QProgressBar#metricProgress[tone="manual"]::chunk { background:#F28A41; }
QProgressBar#metricProgress[tone="critical"]::chunk { background:#DF3657; }
QLabel#automationPreviousMetric { background:#F8FAFC; border:none; font-size:15px; padding:6px; }
QLabel#automationPreviousDate { font-size:12px; font-weight:500; }
QLabel#automationPreviousNote { font-size:10px; }
QWidget#reviewHeadingPanel { background:#FFFFFF; border:1px solid #E7ECF3; border-bottom:none; border-radius:5px; }
QLabel#workflowConnector { color:#A5B8E9; font-size:13px; }
QLabel#automationPreviousSignal { background:#F7F9FC; color:#53657D; padding:9px 5px; font-size:11px; border-radius:5px; }
QPushButton#automationViewTab { color:#536987; background:transparent; font-size:11px; padding:6px 8px; min-width:0; min-height:18px; border:0; border-bottom:2px solid transparent; border-radius:0; }
QPushButton#automationViewTab:checked { color:#264FE4; border-bottom:2px solid #315BE8; }
QPushButton#automationViewTab:hover { color:#264FE4; background:#F1F5FF; }
QLineEdit#automationSearch, QComboBox#automationFilter,
QPushButton#automationToolbarButton { min-height:20px; padding:4px 7px; border-radius:5px; font-size:10px; }
QComboBox#sourceCompactFilter, QLineEdit#sourceCompactSearch { background:white; color:#46566E; border:1px solid #DCE3ED; border-radius:5px; min-height:20px; padding:2px 5px; font-size:10px; }
QComboBox#sourceCompactFilter::drop-down { border:none; width:22px; }
QComboBox#sourceCompactFilter::down-arrow { image:none; }
QTableWidget#attentionTable { font-size:11px; border-radius:5px; }
QTableWidget#attentionTable::item { padding:1px 5px; }
QTableWidget#attentionTable QHeaderView::section,
QTableWidget#dashboardSourceTable QHeaderView::section { min-height:20px; padding:3px; font-size:10px; }
QLabel#recordStatusPill { padding:1px 4px; font-size:10px; border-radius:8px; }
QTableWidget#dashboardSourceTable, QTableWidget#sourceSummaryTable,
QTableWidget#attentionTable {
    color:#203654; background:#FFFFFF; selection-color:#173A79;
    selection-background-color:#E8EFFF; outline:none;
}
QTableWidget#dashboardSourceTable::item { padding:2px 4px; }
QTableWidget#dashboardSourceTable::item:hover, QTableWidget#sourceSummaryTable::item:hover { color:#203654; background:#F3F6FC; }
QTableWidget#dashboardSourceTable::item:selected, QTableWidget#sourceSummaryTable::item:selected,
QTableWidget#attentionTable::item:selected { color:#173A79; background:#E8EFFF; }
QTableWidget#dashboardSourceTable QLineEdit, QTableWidget#sourceSummaryTable QLineEdit {
    color:#203654; background:white; selection-color:white; selection-background-color:#315BE8;
}
QFrame#inspectorPanel { border:1px solid #E3E9F2; border-radius:6px; }
QLabel#inspectorTitle { font-size:14px; font-weight:700; }
QWidget#inspectorEvidence, QScrollArea#inspectorEvidenceScroll { background:white; border:none; }
QLabel#inspectorSectionTitle { font-size:12px; font-weight:700; color:#172033; padding:4px 0; }
QLabel#inspectorKey, QLabel#inspectorValue, QLabel#inspectorNeutral { font-size:12px; color:#536987; }
QLabel#inspectorValue { color:#213F73; }
QLabel#inspectorNeutral { color:#718096; font-size:11px; }
QFrame#inspectorEvidenceRow { background:white; border:none; border-bottom:1px solid #EDF0F5; }
QFrame#confidenceUnavailable { background:#E8EDF5; border:none; border-radius:3px; }
QLabel#inspectorWarning { color:#9F620B; background:#FFF5DF; border:1px solid #F2D496; border-radius:6px; padding:10px; font-size:11px; }
QPushButton#inspectorSecondary { color:#315080; background:white; border:1px solid #DCE3ED; padding:6px 8px; font-size:12px; border-radius:5px; }
QFrame#inspectorPanel QPushButton#primary { min-width:0; min-height:26px; padding:6px 8px; font-size:13px; }
QFrame#operationActionBar QPushButton { min-height:22px; padding:5px 12px; font-size:11px; }
QPushButton.navItem { font-size:12px; font-weight:500; min-height:20px; padding:3px 7px; color:#DCE5F2; }
QPushButton.navItem:hover { background:#23344B; color:white; }
QPushButton#sidebarChevron { color:#C8D5E8; background:transparent; border:none; padding:0; font-size:16px; min-width:0; min-height:0; }
QPushButton#sidebarChevron:hover { background:#23344B; color:white; }
QPushButton#accountingSubnavButton { font-size:12px; padding:4px 8px; min-height:21px; border-radius:4px; }
QFrame#sidebarItem[active="true"] { background:#24364C; border-radius:5px; }
QPushButton.navItem[active="true"] { background:transparent; font-weight:600; color:white; }
QFrame#sidebarItem { padding-top:3px; padding-bottom:3px; }
QLabel#automationReconHint { font-size:10px; color:#64748B; }
QLabel#automationReconSupplement { font-size:10px; color:#365589; background:#F0F4FC; border-radius:4px; padding:4px 6px; }
QLabel#automationMetricLabel, QLabel#automationReconLabel { font-size:11px; }
QLabel#automationMetricValue { font-size:15px; font-weight:700; }
QTableWidget#dashboardSourceTable { font-size:11px; }
QTableWidget#dashboardSourceTable:disabled, QTableWidget#sourceSummaryTable:disabled { color:#64748B; background:#F5F7FA; selection-color:#334155; selection-background-color:#E8EDF5; }
QTableWidget#dashboardSourceTable::item:selected:!active, QTableWidget#sourceSummaryTable::item:selected:!active { color:#173A79; background:#E8EFFF; }
QWidget#accountingOutputsPage { background:#F6F8FC; }
QTableWidget#operationBreakdownTable { background:white; color:#243B53; border:1px solid #E3E9F2; border-radius:5px; gridline-color:#EDF1F6; font-size:11px; selection-color:#173A79; selection-background-color:#E8EFFF; }
QTableWidget#operationBreakdownTable::item { padding:3px 5px; }
QTableWidget#operationBreakdownTable::item:selected { color:#173A79; background:#E8EFFF; }
QTableWidget#operationBreakdownTable QHeaderView::section { background:#F7F9FC; color:#4B6180; font-size:11px; font-weight:600; border:none; border-bottom:1px solid #E0E7F0; padding:7px; }
QComboBox#operationSelector { background:white; color:#243B53; border:1px solid #DCE3ED; padding:6px 10px; min-height:26px; border-radius:6px; }
QTabBar#inspectorTabs::tab { padding:6px; font-size:11px; }
QFrame#inspectorPanel QPushButton#primary { min-height:22px; padding:5px 8px; font-size:12px; }
QPushButton#inspectorSecondary { padding:4px 8px; font-size:11px; }
"""

# 2026-09-17 manual parity pass — latest approved finance-workspace mockup.
MAIN_STYLE += """
/* ===== Latest approved compact finance workspace ===== */
QFrame#workspaceHeader {
    min-height:36px;
    max-height:36px;
    background:#FFFFFF;
    border-bottom:1px solid #E5EAF1;
}
QLabel#workspaceHeading { color:#607089; font-size:10px; font-weight:500; }
QPushButton#topbarTextAction { color:#334F7E; font-size:10px; padding:4px 7px; }
QLineEdit#globalSearch {
    min-height:22px; max-height:22px;
    background:#FBFCFE; color:#7B8798;
    border:1px solid #DCE3ED; border-radius:7px;
    padding:0 10px; font-size:10px;
}
QPushButton#topbarIconAction {
    color:#304E7B; background:transparent; border:none; font-size:14px;
}

QWidget#automationCanvas { background:#F7F9FC; }
QLabel#automationPageTitle { color:#111827; font-size:22px; font-weight:700; }
QLabel#automationPageSubtitle { color:#405A83; font-size:11px; }
QLabel#automationTitleIcon { color:#315BE8; }
QLabel#automationHeaderState {
    padding:3px 7px; border-radius:6px; font-size:9px; font-weight:600;
}
QFrame#automationSummaryRail {
    min-height:52px; max-height:58px;
    background:#FFFFFF; border:1px solid #E1E7EF; border-radius:8px;
}
QFrame#automationStatBlock { background:transparent; border:none; }
QLabel#automationStatValue { color:#111827; font-size:13px; font-weight:700; }
QLabel#automationStatDetail { color:#70819A; font-size:9px; }
QPushButton#automationAddSource {
    min-height:20px; padding:5px 11px;
    background:#FFFFFF; color:#2F59E8;
    border:1px solid #6F88F7; border-radius:7px;
    font-size:10px; font-weight:700;
}
QPushButton#automationClearSource { padding:5px 6px; font-size:9px; }

QFrame#automationStepRail {
    min-height:38px; max-height:42px;
    background:#FFFFFF; border:none; border-radius:6px;
}
QLabel#automationStepNumber { font-size:9px; border-radius:11px; }
QLabel#automationStepTitle { color:#566986; font-size:10px; font-weight:500; }
QLabel#automationStepTitle[stepState="active"] { color:#315BE8; font-weight:700; }
QLabel#workflowConnector { color:#98ACE0; font-size:11px; }

QFrame#automationMetricStrip {
    background:#FFFFFF; border:1px solid #E3E8F0; border-radius:8px;
}
QFrame#automationMetricTile { background:#F7F9FC; border:none; border-radius:7px; }
QLabel#automationMetricLabel { color:#53657D; font-size:10px; font-weight:500; }
QLabel#automationMetricValue { color:#111827; font-size:14px; font-weight:700; }
QLabel#automationMetricDetail { color:#6F7E93; font-size:9px; }
QLabel#automationMetricIcon { font-size:15px; border-radius:9px; }
QLabel#automationMetricIcon[tone="success"] { background:#E6F7EE; color:#0A9D63; }
QLabel#automationMetricIcon[tone="critical"] { background:#FCE7EB; color:#E12D4F; }
QLabel#automationMetricIcon[tone="warning"] { background:#FFF1D3; color:#DA9400; }
QLabel#automationMetricIcon[tone="manual"] { background:#FFF0E4; color:#E7731B; }
QLabel#automationMetricIcon[tone="info"] { background:#EDF1FF; color:#315BE8; }
QProgressBar#metricProgress { min-height:3px; max-height:3px; }

QFrame#automationReconciliationStrip {
    background:#FFFFFF; border:1px solid #DDE5EF; border-radius:8px;
}
QLabel#automationReconTitle { color:#172033; font-size:12px; font-weight:700; }
QLabel#automationReconLabel { color:#65758B; font-size:9px; }
QLabel#automationReconValue { color:#111827; font-size:13px; font-weight:700; }
QFrame#automationReconCell { background:transparent; border:none; border-right:1px solid #E6EBF2; }
QFrame#automationReconCell[tone="success"] {
    background:#EAF8F1; border:1px solid #CDEEDD; border-radius:7px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF6E5; border:1px solid #F0D699; border-radius:7px;
}

QFrame#automationSourcePanel,
QFrame#automationPreviousPanel {
    background:#FFFFFF; border:1px solid #DFE6EF; border-radius:8px;
}
QLabel#automationCompactTitle { color:#172033; font-size:11px; font-weight:700; }
QLabel#automationCompactBadge {
    color:#315BE8; background:#EEF2FF; border:none; border-radius:8px;
    padding:2px 7px; font-size:8px; font-weight:700;
}
QComboBox#sourceCompactFilter, QLineEdit#sourceCompactSearch {
    min-height:18px; padding:2px 5px; font-size:9px; border-radius:5px;
}
QPushButton#automationCompactButton { min-height:18px; padding:3px 7px; font-size:9px; }
QTableWidget#dashboardSourceTable { font-size:10px; gridline-color:#E7ECF3; }
QTableWidget#dashboardSourceTable::item { padding:1px 4px; }
QTableWidget#dashboardSourceTable QHeaderView::section {
    background:#F8FAFD; color:#435775; font-size:9px; font-weight:650;
    min-height:18px; padding:2px 3px; border:none; border-bottom:1px solid #E0E7F0;
}
QTableWidget#operationBreakdownTable { font-size:10px; }
QTableWidget#operationBreakdownTable::item { padding:2px 5px; }

QWidget#reviewHeadingPanel { background:#FFFFFF; border:1px solid #E4E9F1; border-bottom:none; border-radius:6px; }
QLabel#automationSectionTitle { color:#172033; font-size:12px; font-weight:700; }
QPushButton#automationViewTab { color:#536987; font-size:10px; padding:4px 7px; min-height:16px; }
QLineEdit#automationSearch, QComboBox#automationFilter,
QPushButton#automationToolbarButton { min-height:18px; padding:3px 6px; font-size:9px; }
QTableWidget#attentionTable { font-size:10px; }
QTableWidget#attentionTable QHeaderView::section { min-height:18px; padding:3px 5px; font-size:9px; }

QFrame#inspectorPanel {
    background:#FFFFFF; border:1px solid #E2E8F1; border-radius:7px;
}
QLabel#inspectorTitle { color:#172033; font-size:12px; font-weight:700; }
QLabel#inspectorMeta { color:#758399; font-size:8px; }
QPushButton#inspectorNavButton {
    background:#FFFFFF; color:#315080; border:1px solid #DDE4ED;
    border-radius:6px; padding:0; font-size:12px;
}
QTabBar#inspectorTabs::tab { padding:5px 5px; font-size:10px; }
QLabel#inspectorSectionTitle { color:#172033; font-size:10px; font-weight:700; padding:2px 0; }
QLabel#inspectorKey, QLabel#inspectorValue { font-size:10px; }
QLabel#inspectorNeutral { font-size:9px; }
QFrame#inspectorEvidenceRow { border-bottom:1px solid #EEF1F5; }
QLabel#inspectorWarning {
    color:#9B610B; background:#FFF5DF; border:1px solid #F0D49A;
    border-radius:6px; padding:7px; font-size:9px;
}
QFrame#inspectorPanel QPushButton#primary { min-height:22px; padding:5px 7px; font-size:10px; }
QPushButton#inspectorSecondary { min-height:20px; padding:4px 6px; font-size:9px; }

/* Sidebar: target density, semantic status dot, fixed settings near profile. */
QFrame#sidebar { background:#101E32; border-right:1px solid #26384F; }
QFrame#brandArea { padding:0; }
QFrame#companyCard {
    background:#12243B; border:1px solid #314A68; border-radius:7px;
}
QLabel#companyCardName { color:#F7F9FC; font-size:10px; font-weight:700; }
QLabel#companyCardHint { color:#8FA3BE; font-size:8px; }
QPushButton#companyCardChevron {
    color:#B9C8DA; background:transparent; border:none; border-radius:5px;
    padding:0; font-size:12px;
}
QPushButton#companyCardChevron:hover { background:#1B304B; color:#FFFFFF; }
QFrame#sidebarItem { padding-top:1px; padding-bottom:1px; background:transparent; }
QFrame#sidebarItem[active="true"] {
    background:#23364E; border-left:3px solid #315BE8; border-radius:5px;
}
QPushButton.navItem {
    color:#D7E0EC; background:transparent; border:none;
    min-height:19px; padding:2px 6px; font-size:10px; font-weight:500; text-align:left;
}
QPushButton.navItem[active="true"] { color:#FFFFFF; font-weight:700; background:transparent; }
QPushButton#sidebarChevron { font-size:13px; color:#B9C8DA; }
QFrame#accountingSubnav { border-left:1px solid #2C425F; margin-left:8px; }
QPushButton#accountingSubnavButton {
    color:#C1CCDB; background:transparent; border:none; border-radius:5px;
    min-height:17px; padding:2px 7px; font-size:10px; text-align:left;
}
QPushButton#accountingSubnavButton[active="true"] {
    color:#FFFFFF; background:#315BE8; font-weight:700;
}
QPushButton#sidebarFixedSettings {
    color:#D7E0EC; background:transparent; border:none; border-top:1px solid #273A52;
    border-radius:0; text-align:left; min-height:30px; padding:5px 8px; font-size:10px;
}
QPushButton#sidebarFixedSettings:hover { background:#172A44; color:#FFFFFF; }
QPushButton#sidebarFixedSettings[active="true"] { color:#FFFFFF; background:#23364E; font-weight:700; }
QFrame#userCard { border-top:none; padding:0; }
QLabel#userName { font-size:10px; font-weight:600; }
QLabel#userStatus { font-size:8px; }
"""

# 2026-09-18 manual parity pass 2 — density, semantic colour, inspector fidelity.
MAIN_STYLE += """
/* ===== Pass 2: compact finance-operations parity ===== */
QFrame#workspaceHeader { min-height:34px; max-height:34px; }
QPushButton#topbarTextAction { min-height:22px; padding:3px 6px; font-size:10px; }
QLineEdit#globalSearch { min-height:22px; max-height:22px; padding:0 9px; }
QPushButton#topbarIconAction { min-width:28px; max-width:28px; min-height:28px; max-height:28px; }

QLabel#automationPageTitle { font-size:21px; font-weight:700; }
QLabel#automationPageSubtitle { font-size:10px; color:#496086; }
QFrame#automationSummaryRail { min-height:48px; max-height:52px; }
QLabel#automationStatValue { font-size:12px; font-weight:700; }
QLabel#automationStatDetail { font-size:8px; color:#71829B; }
QFrame#automationStepRail { min-height:33px; max-height:35px; }
QLabel#automationStepNumber { font-size:8px; border-radius:10px; }
QLabel#automationStepTitle { font-size:9px; }
QLabel#workflowConnector { font-size:9px; }

QFrame#automationMetricStrip { min-height:70px; max-height:74px; }
QFrame#automationMetricTile { border:1px solid transparent; border-radius:7px; }
QFrame#automationMetricTile[tone="success"] { background:#F3FAF7; border-color:#E5F3EC; }
QFrame#automationMetricTile[tone="critical"] { background:#FFF6F7; border-color:#F8E7EA; }
QFrame#automationMetricTile[tone="warning"] { background:#FFF9ED; border-color:#F8EBCF; }
QFrame#automationMetricTile[tone="manual"] { background:#FFF7F0; border-color:#F6E6D8; }
QFrame#automationMetricTile[tone="info"] { background:#F5F7FF; border-color:#E7EBFA; }
QLabel#automationMetricLabel { font-size:9px; color:#556982; }
QLabel#automationMetricValue { font-size:13px; font-weight:700; }
QLabel#automationMetricDetail { font-size:8px; color:#77869A; }
QLabel#automationMetricIcon { font-size:14px; }

QFrame#automationReconciliationStrip { min-height:62px; max-height:66px; }
QLabel#automationReconTitle { font-size:11px; font-weight:700; }
QLabel#automationReconLabel { font-size:8px; color:#687A92; }
QLabel#automationReconValue { font-size:12px; font-weight:700; }
QFrame#automationReconCell[tone="success"] { background:#EAF8F1; border-color:#CFECDC; }

QFrame#automationSourcePanel, QFrame#automationPreviousPanel { border-radius:7px; }
QLabel#automationCompactTitle { font-size:10px; font-weight:700; }
QLabel#automationCompactBadge { font-size:8px; padding:1px 6px; }
QComboBox#sourceCompactFilter, QLineEdit#sourceCompactSearch {
    min-height:17px; max-height:20px; padding:1px 5px; font-size:8px;
}
QPushButton#automationCompactButton { min-height:17px; padding:2px 6px; font-size:8px; }
QTableWidget#dashboardSourceTable { font-size:9px; }
QTableWidget#dashboardSourceTable QHeaderView::section { min-height:17px; padding:1px 3px; font-size:8px; }
QTableWidget#operationBreakdownTable { font-size:9px; }
QTableWidget#operationBreakdownTable::item { padding:1px 4px; }

QWidget#reviewHeadingPanel { border-radius:6px; }
QLabel#automationSectionTitle { font-size:11px; font-weight:700; }
QPushButton#automationViewTab { min-height:15px; padding:3px 6px; font-size:9px; }
QLineEdit#automationSearch, QComboBox#automationFilter, QPushButton#automationToolbarButton {
    min-height:17px; max-height:22px; padding:2px 5px; font-size:8px;
}
QTableWidget#attentionTable { font-size:9px; }
QTableWidget#attentionTable QHeaderView::section { min-height:17px; padding:2px 4px; font-size:8px; }
QLabel#recordStatusPill { font-size:9px; }
QLabel#automationFooterText { font-size:8px; }
QPushButton#automationPagerButton { min-width:24px; max-width:24px; min-height:20px; max-height:20px; }

QFrame#operationActionBar { min-height:34px; max-height:38px; }
QFrame#operationActionBar QLabel { font-size:10px; }
QFrame#operationActionBar QPushButton { min-height:20px; padding:4px 9px; font-size:9px; }

QFrame#inspectorPanel { border-radius:7px; }
QLabel#inspectorTitle { font-size:11px; font-weight:700; }
QLabel#inspectorMeta { font-size:8px; color:#7A879A; }
QPushButton#inspectorNavButton { border-radius:5px; font-size:11px; }
QTabBar#inspectorTabs::tab { padding:4px 5px; min-height:18px; font-size:9px; }
QLabel#inspectorSectionTitle { font-size:9px; font-weight:700; padding:1px 0; }
QLabel#inspectorKey { color:#687991; font-size:9px; }
QLabel#inspectorValue { color:#294D85; font-size:9px; }
QLabel#inspectorNeutral { color:#8A96A8; font-size:8px; }
QFrame#inspectorEvidenceRow { border-bottom:1px solid #EEF2F6; }
QFrame#confidenceUnavailable { background:#E8EDF4; border-radius:2px; }
QLabel#inspectorWarning { padding:5px 6px; font-size:8px; }
QFrame#inspectorPanel QPushButton#primary { min-height:20px; padding:4px 7px; font-size:9px; }
QPushButton#inspectorSecondary { min-height:18px; padding:3px 5px; font-size:8px; }

QFrame#sidebar { background:#102036; border-right:1px solid #263A54; }
QFrame#companyCard { background:#132740; border-color:#334C69; border-radius:6px; }
QLabel#companyCardName { font-size:9px; font-weight:700; }
QLabel#companyCardHint { font-size:7px; }
QFrame#sidebarItem { padding-top:0; padding-bottom:0; }
QPushButton.navItem { min-height:18px; padding:1px 5px; font-size:9px; font-weight:500; }
QPushButton.navItem[active="true"] { font-weight:700; }
QPushButton#sidebarChevron { font-size:11px; }
QFrame#accountingSubnav { margin-left:7px; }
QPushButton#accountingSubnavButton { min-height:16px; padding:1px 6px; font-size:9px; }
QPushButton#sidebarFixedSettings { min-height:27px; padding:4px 7px; font-size:9px; }
QLabel#userName { font-size:9px; font-weight:600; }
QLabel#userStatus { font-size:7px; }
"""

# 2026-09-18 manual parity pass 3 — restore mockup proportions and exact visual language.
MAIN_STYLE += """
/* ===== Pass 3: approved mockup parity, not extra compression ===== */
/* Sidebar uses the charcoal-navy from the approved mockup. */
QFrame#sidebar {
    background:#1B2634;
    border-right:1px solid #2B394B;
}
QFrame#brandArea { padding:2px 2px 4px 2px; }
QFrame#companyCard {
    background:#1D2937;
    border:1px solid #34465D;
    border-radius:7px;
    min-height:42px;
}
QFrame#companyCard:hover { background:#223044; border-color:#49617D; }
QLabel#companyCardName { color:#F5F7FB; font-size:11px; font-weight:700; }
QLabel#companyCardHint { color:#9BAABD; font-size:9px; }
QPushButton#companyCardChevron { color:#C0CBDA; font-size:12px; }

/* Parent rows are deliberately readable again; Pass 2 made them too small. */
QFrame#sidebarItem {
    background:transparent;
    border:none;
    padding-top:1px;
    padding-bottom:1px;
}
QFrame#sidebarItem[active="true"] {
    background:#263345;
    border-left:3px solid #3566EB;
    border-radius:5px;
}
QPushButton.navItem {
    color:#DFE6EF;
    background:transparent;
    border:none;
    min-height:27px;
    padding:4px 7px;
    font-size:11px;
    font-weight:500;
    text-align:left;
}
QPushButton.navItem:hover { background:#243245; color:#FFFFFF; }
QPushButton.navItem[active="true"] { color:#FFFFFF; background:transparent; font-weight:700; }
QPushButton#sidebarChevron { color:#C3CEDC; font-size:12px; }
QFrame#accountingSubnav {
    border-left:1px solid #35475D;
    margin-left:9px;
}
QPushButton#accountingSubnavButton {
    color:#CDD6E2;
    background:transparent;
    border:none;
    border-radius:5px;
    min-height:24px;
    padding:4px 8px;
    font-size:10px;
    text-align:left;
}
QPushButton#accountingSubnavButton:hover { background:#243245; color:#FFFFFF; }
QPushButton#accountingSubnavButton[active="true"] {
    color:#FFFFFF;
    background:#315BE8;
    font-weight:700;
}
QPushButton#sidebarFixedSettings {
    color:#E0E6EE;
    background:transparent;
    border:none;
    border-top:1px solid #334257;
    border-radius:0;
    text-align:left;
    min-height:34px;
    padding:7px 8px;
    font-size:11px;
}
QPushButton#sidebarFixedSettings:hover { background:#243245; color:#FFFFFF; }
QPushButton#sidebarFixedSettings[active="true"] { background:#263345; color:#FFFFFF; font-weight:700; }
QFrame#userCard { background:transparent; border:none; border-top:none; padding:1px 0 0 0; }
QLabel#sidebarAvatar { background:#315BE8; color:#FFFFFF; }
QLabel#userName { color:#F4F7FB; font-size:11px; font-weight:600; }
QLabel#userStatus { color:#97A8BC; font-size:9px; }
QPushButton#logoutButton { color:#B7C4D4; }

/* Canvas and cards: white surfaces on the cool off-white approved background. */
QWidget#automationCanvas,
QScrollArea#automationCanvasScroll,
QScrollArea#automationCanvasScroll > QWidget > QWidget,
QWidget#accountingWorkspace { background:#F6F8FB; }
QFrame#automationSummaryRail,
QFrame#automationStepRail,
QFrame#automationReconciliationStrip,
QFrame#automationSourcePanel,
QFrame#automationPreviousPanel,
QWidget#reviewHeadingPanel {
    background:#FFFFFF;
    border-color:#E1E7EF;
}

/* Metric strip in the mockup is white; semantic colour belongs to icon/progress, not the whole tile. */
QFrame#automationMetricStrip { background:transparent; border:none; }
QFrame#automationMetricTile,
QFrame#automationMetricTile[tone="success"],
QFrame#automationMetricTile[tone="critical"],
QFrame#automationMetricTile[tone="warning"],
QFrame#automationMetricTile[tone="manual"],
QFrame#automationMetricTile[tone="info"] {
    background:#FFFFFF;
    border:1px solid #E3E8F0;
    border-radius:8px;
}
QLabel#automationMetricIcon[tone="success"] { background:#E4F8EE; color:#0DA66A; }
QLabel#automationMetricIcon[tone="critical"] { background:#FDE7EC; color:#E42B4F; }
QLabel#automationMetricIcon[tone="warning"] { background:#FFF2D0; color:#E7A10A; }
QLabel#automationMetricIcon[tone="manual"] { background:#FFF0E1; color:#F27A18; }
QLabel#automationMetricIcon[tone="info"] { background:#EDF2FF; color:#3566EB; }
QFrame#decisionBar { background:#E9EEF5; }
QFrame#decisionBarSegment[tone="success"] { background:#18B77A; }
QFrame#decisionBarSegment[tone="warning"] { background:#F6B516; }
QFrame#decisionBarSegment[tone="manual"] { background:#F08A1C; }
QFrame#decisionBarSegment[tone="critical"] { background:#E62D50; }

/* Mutabakat: only Fark is a semantic filled cell in the reference. */
QFrame#automationReconCell { background:transparent; border:none; border-right:1px solid #E6EBF2; }
QFrame#automationReconCell[tone="success"] {
    background:#EAF8F1;
    border:1px solid #CFECDC;
    border-radius:7px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF4DB;
    border:1px solid #F2D99D;
    border-radius:7px;
}

/* Review table mirrors the blue selected row and semantic pills from the target. */
QTableWidget#attentionTable {
    background:#FFFFFF;
    alternate-background-color:#FBFCFE;
    gridline-color:#E5EAF1;
    selection-background-color:#E9F0FF;
    selection-color:#172033;
}
QTableWidget#attentionTable::item:selected { background:#E9F0FF; color:#172033; }
QLabel#recordStatusPill[tone="success"] { background:#DFF7EB; color:#087A4B; }
QLabel#recordStatusPill[tone="warning"] { background:#FFF0C8; color:#9B6200; }
QLabel#recordStatusPill[tone="critical"] { background:#FFE2E7; color:#C11E39; }

/* Inspector: same typography, stronger semantic colour and section hierarchy. */
QFrame#inspectorPanel {
    background:#FFFFFF;
    border:1px solid #E1E7EF;
    border-radius:7px;
}
QLabel#inspectorStatusPill {
    border:none;
    border-radius:10px;
    padding:4px 8px;
    font-size:9px;
    font-weight:700;
}
QLabel#inspectorStatusPill[tone="success"] { background:#E7F8EF; color:#087A4B; }
QLabel#inspectorStatusPill[tone="warning"] { background:#FFF0D5; color:#AD6800; }
QLabel#inspectorStatusPill[tone="critical"] { background:#FDE7EC; color:#C11E39; }
QLabel#inspectorStatusPill[tone="info"] { background:#EDF2FF; color:#315BE8; }
QTabBar#inspectorTabs::tab {
    background:#FFFFFF;
    color:#667085;
    border:none;
    border-bottom:2px solid transparent;
}
QTabBar#inspectorTabs::tab:selected { color:#315BE8; border-bottom:2px solid #315BE8; font-weight:700; }
QLabel#inspectorSectionTitle { color:#172033; font-weight:700; }
QFrame#inspectorEvidenceRow { background:#FFFFFF; border:none; border-bottom:1px solid #EDF1F5; }
QLabel#inspectorEvidenceIcon {
    background:transparent;
    border:none;
    font-size:12px;
    font-weight:800;
}
QLabel#inspectorEvidenceIcon[tone="success"] { color:#14A66C; }
QLabel#inspectorEvidenceIcon[tone="warning"] { color:#E9A11B; }
QLabel#inspectorEvidenceIcon[tone="critical"] { color:#E24B4B; }
QLabel#inspectorEvidenceIcon[tone="info"] { color:#3978E6; }
QLabel#inspectorEvidenceIcon[tone="neutral"] { color:#98A2B3; }
QLabel#inspectorValue { color:#294D85; }
QFrame#confidenceUnavailable { background:#E7ECF3; border-radius:3px; }
QLabel#inspectorWarning {
    color:#9A610B;
    background:#FFF3D7;
    border:1px solid #F0D198;
    border-radius:6px;
}
QFrame#inspectorPanel QPushButton#primary {
    background:#3566EB;
    border-color:#3566EB;
    color:#FFFFFF;
}
QFrame#inspectorPanel QPushButton#primary:hover { background:#2D58D2; border-color:#2D58D2; }
QPushButton#inspectorSecondary { background:#FFFFFF; color:#315080; border:1px solid #D9E1EB; }
QPushButton#inspectorSecondary:hover { background:#F6F8FC; border-color:#BCC9DA; }
"""

# 2026-09-18 manual parity pass 4 — restore content readability and target colour fidelity.
MAIN_STYLE += """
/* ===== Pass 4: exact mockup readability + semantic colour ===== */
/* The target sidebar is a charcoal navy. Parent rows intentionally occupy
   the full rail when the accounting submenu is closed; expanded mode scrolls. */
QFrame#sidebar { background:#1C2734; border-right:1px solid #2A394B; }
QFrame#companyCard { background:#1D2937; border-color:#35475D; }
QFrame#sidebarItem {
    min-height:46px;
    background:transparent;
    border:none;
    padding:0;
}
QFrame#sidebarItem[active="true"] {
    background:#263445;
    border-left:4px solid #4772FC;
    border-radius:5px;
}
QPushButton.navItem {
    color:#E0E7F0;
    min-height:30px;
    padding:5px 7px;
    font-size:12px;
    font-weight:500;
}
QPushButton.navItem:hover { background:#243345; color:#FFFFFF; }
QPushButton.navItem[active="true"] { color:#FFFFFF; font-weight:700; }
QFrame#accountingSubnav { border-left:1px solid #35485F; margin-left:10px; }
QPushButton#accountingSubnavButton {
    color:#D0D9E5;
    min-height:25px;
    padding:4px 9px;
    font-size:11px;
}
QPushButton#accountingSubnavButton:hover { background:#243345; color:#FFFFFF; }
QPushButton#accountingSubnavButton[active="true"] {
    color:#FFFFFF;
    background:#304EAE;
    font-weight:700;
}
QPushButton#sidebarFixedSettings {
    min-height:36px;
    padding:7px 8px;
    font-size:12px;
    color:#E1E7EF;
    border-top:1px solid #354254;
}
QLabel#userName { font-size:11px; }
QLabel#userStatus { font-size:9px; }

/* Main work surface: keep Pass-3 geometry, restore the typography scale of
   the approved mockup. No card is made taller here. */
QLabel#automationPageTitle { font-size:23px; font-weight:700; }
QLabel#automationPageSubtitle { font-size:12px; color:#405783; }
QLabel#automationStatValue { font-size:14px; font-weight:700; color:#172033; }
QLabel#automationStatDetail { font-size:10px; color:#6C7E96; }
QLabel#automationStepNumber { font-size:9px; }
QLabel#automationStepTitle { font-size:11px; color:#536987; }
QLabel#automationStepTitle[stepState="active"] { color:#315BE8; font-weight:700; }
QLabel#workflowConnector { color:#9EB2E7; font-size:11px; }

QLabel#automationMetricLabel { color:#53657D; font-size:11px; font-weight:500; }
QLabel#automationMetricValue { color:#111827; font-size:16px; font-weight:700; }
QLabel#automationMetricDetail { color:#6F7E93; font-size:10px; }
QLabel#automationMetricIcon { font-size:16px; }
QProgressBar#metricProgress { background:#E8EDF4; }
QProgressBar#metricProgress[tone="success"]::chunk { background:#17B878; }
QProgressBar#metricProgress[tone="warning"]::chunk { background:#F5B41B; }
QProgressBar#metricProgress[tone="manual"]::chunk { background:#F18A20; }
QProgressBar#metricProgress[tone="critical"]::chunk { background:#E43052; }

QLabel#automationReconTitle { color:#172033; font-size:13px; font-weight:700; }
QLabel#automationReconLabel { color:#66778E; font-size:10px; }
QLabel#automationReconValue { color:#111827; font-size:14px; font-weight:700; }
QFrame#automationReconCell[tone="success"] { background:#ECFAF3; border-color:#D4F0E1; }
QFrame#automationReconCell[tone="warning"] { background:#FFF5DE; border-color:#F2D79A; }

QLabel#automationCompactTitle { color:#172033; font-size:12px; font-weight:700; }
QLabel#automationCompactBadge {
    color:#315BE8; background:#EEF2FF; padding:2px 7px; font-size:9px; font-weight:700;
}
QComboBox#sourceCompactFilter, QLineEdit#sourceCompactSearch {
    font-size:10px; color:#465A77; background:#FFFFFF; border-color:#DCE3ED;
}
QPushButton#automationCompactButton { font-size:10px; color:#315BE8; }
QTableWidget#dashboardSourceTable,
QTableWidget#operationBreakdownTable {
    color:#263B59;
    font-size:11px;
    gridline-color:#E6EBF2;
}
QTableWidget#dashboardSourceTable QHeaderView::section,
QTableWidget#operationBreakdownTable QHeaderView::section {
    background:#F7F9FC;
    color:#425875;
    font-size:10px;
    font-weight:650;
    border-bottom:1px solid #DFE6EF;
}

QLabel#automationSectionTitle { color:#172033; font-size:13px; font-weight:700; }
QPushButton#automationViewTab { color:#526986; font-size:11px; }
QPushButton#automationViewTab:checked { color:#315BE8; border-bottom-color:#315BE8; font-weight:700; }
QLineEdit#automationSearch, QComboBox#automationFilter, QPushButton#automationToolbarButton {
    color:#425875;
    background:#FFFFFF;
    font-size:10px;
}
QTableWidget#attentionTable {
    color:#263B59;
    font-size:11px;
    gridline-color:#E5EAF1;
}
QTableWidget#attentionTable QHeaderView::section {
    background:#F7F9FC;
    color:#425875;
    min-height:19px;
    font-size:10px;
    font-weight:650;
    border-bottom:1px solid #DFE6EF;
}
QLabel#recordStatusPill { font-size:10px; font-weight:650; }
QLabel#recordStatusPill[tone="success"] { background:#DFF7EB; color:#087A4B; }
QLabel#recordStatusPill[tone="warning"] { background:#FFF0C8; color:#9B6200; }
QLabel#recordStatusPill[tone="critical"] { background:#FFE2E7; color:#C11E39; }

/* Inspector keeps its accepted type scale; this pass only brings its semantic
   colour treatment in line with the reference. */
QLabel#inspectorStatusPill { padding:4px 9px; font-weight:700; }
QLabel#inspectorStatusPill[tone="success"] { background:#E5F8ED; color:#087A4B; }
QLabel#inspectorStatusPill[tone="warning"] { background:#FFF0CE; color:#A96500; }
QLabel#inspectorStatusPill[tone="critical"] { background:#FDE5EA; color:#BF1F3B; }
QLabel#inspectorStatusPill[tone="info"] { background:#EAF0FF; color:#315BE8; }
QTabBar#inspectorTabs::tab:selected { color:#315BE8; border-bottom:2px solid #315BE8; font-weight:700; }
QLabel#inspectorEvidenceIcon {
    min-width:16px; max-width:16px;
    min-height:16px; max-height:16px;
    border-radius:8px;
    color:#FFFFFF;
    font-size:10px;
    font-weight:800;
}
QLabel#inspectorEvidenceIcon[tone="success"] { background:#18B779; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="warning"] { background:#F2A71A; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="critical"] { background:#E33250; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="info"] { background:#3566EB; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="neutral"] { background:#A7B0BF; color:#FFFFFF; }
QLabel#inspectorValue { color:#254C8A; }
QLabel#inspectorValue[emphasis="true"] { color:#173F8A; font-weight:700; }
QLabel#inspectorWarning {
    color:#9B610B; background:#FFF2D5; border:1px solid #F0CF8C;
}
QFrame#inspectorPanel QPushButton#primary {
    background:#3567EF; border-color:#3567EF; color:#FFFFFF; font-weight:700;
}
QFrame#inspectorPanel QPushButton#primary:hover { background:#2E5DDB; border-color:#2E5DDB; }
QPushButton#inspectorSecondary { color:#315080; background:#FFFFFF; border-color:#D9E1EB; }
"""

# 2026-09-18 manual parity pass 5 — compact source header + analytical bank breakdown.
MAIN_STYLE += """
/* ===== Pass 5: requested micro-polish ===== */
/* Pull module status text closer to its parent title without changing the
   approved active-row treatment. */
QFrame#sidebarItem { min-height:43px; }
QPushButton.navItem { min-height:27px; padding:4px 7px 2px 7px; }

/* Source summary: one compact header rail, no visually empty action row. */
QFrame#automationSourcePanel { background:#FFFFFF; border:1px solid #DDE5EF; }
QFrame#automationSourcePanel QLabel#automationStatDetail {
    color:#7A899E;
    font-size:9px;
}
QFrame#automationSourcePanel QComboBox#sourceCompactFilter,
QFrame#automationSourcePanel QLineEdit#sourceCompactSearch {
    min-height:22px;
    max-height:24px;
    border-radius:6px;
}
QFrame#automationSourcePanel QPushButton#automationCompactButton {
    min-height:22px;
    padding:2px 8px;
    border:1px solid #D8E1EE;
    border-radius:6px;
    background:#FFFFFF;
}
QFrame#automationSourcePanel QPushButton#automationCompactButton:hover {
    background:#F5F8FF;
    border-color:#BFCDF0;
}

/* The current-operation card is now an analytical bank/category surface, not
   a flat mini-table. */
QFrame#automationPreviousPanel {
    background:#FBFCFF;
    border:1px solid #D7E1EE;
    border-radius:8px;
}
QLabel#automationBreakdownTotal {
    color:#173A79;
    background:#EEF3FF;
    border:1px solid #D9E4FF;
    border-radius:8px;
    padding:3px 8px;
    font-size:10px;
    font-weight:700;
}
QLabel#automationBreakdownContext {
    color:#74849A;
    font-size:9px;
    padding-left:1px;
}
QComboBox#breakdownFilter {
    background:#FFFFFF;
    color:#344B6B;
    border:1px solid #D8E1EC;
    border-radius:6px;
    min-height:22px;
    max-height:24px;
    padding:2px 22px 2px 6px;
    font-size:9px;
}
QComboBox#breakdownFilter:hover { border-color:#B9C8DC; background:#FFFFFF; }
QComboBox#breakdownFilter::drop-down { border:none; width:20px; }
QComboBox#breakdownFilter::down-arrow { image:none; }
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    background:#FFFFFF;
    border:1px solid #E1E7EF;
    border-radius:6px;
    color:#2A4160;
    font-size:10px;
    gridline-color:#E8EDF4;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    background:#F4F7FB;
    color:#60728A;
    min-height:19px;
    padding:2px 5px;
    font-size:9px;
    font-weight:650;
    border:none;
    border-bottom:1px solid #E1E7EF;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable::item {
    padding:2px 6px;
    border:none;
    border-bottom:1px solid #EDF1F5;
}
QFrame#automationPreviousPanel QPushButton#automationCompactButton {
    min-height:22px;
    color:#315BE8;
    background:#FFFFFF;
    border:1px solid #D8E1EE;
    border-radius:6px;
    font-weight:600;
}
QFrame#automationPreviousPanel QPushButton#automationCompactButton:hover {
    background:#F2F6FF;
    border-color:#BFCDF0;
}
"""

# 2026-09-18 manual parity pass 6 — finish the four approved polish targets.
MAIN_STYLE += """
/* ===== Pass 6: finished sidebar rhythm + analytical card + type/colour ===== */
/* Sidebar: title + module state read as one group. Closed accounting submenu
   gets its extra vertical rhythm from MainWindow._sync_sidebar_density(). */
QFrame#sidebarItem { min-height:40px; }
QPushButton.navItem {
    min-height:24px;
    padding:3px 7px 0 7px;
    font-size:12px;
    font-weight:550;
}

/* KPI cards: white finance cards, larger semantic icon discs and stronger
   value hierarchy. Colour remains semantic instead of tinting whole cards. */
QFrame#automationMetricStrip { min-height:74px; max-height:78px; }
QFrame#automationMetricTile,
QFrame#automationMetricTile[tone="success"],
QFrame#automationMetricTile[tone="critical"],
QFrame#automationMetricTile[tone="warning"],
QFrame#automationMetricTile[tone="manual"],
QFrame#automationMetricTile[tone="info"] {
    background:#FFFFFF;
    border:1px solid #E2E8F0;
    border-radius:8px;
}
QLabel#automationMetricIcon {
    min-width:28px; max-width:28px;
    min-height:28px; max-height:28px;
    border-radius:14px;
    font-size:17px;
    font-weight:700;
}
QLabel#automationMetricLabel { color:#53657D; font-size:11px; font-weight:550; }
QLabel#automationMetricValue { color:#0F172A; font-size:16px; font-weight:750; }
QLabel#automationMetricDetail { color:#718096; font-size:10px; }
QProgressBar#metricProgress { min-height:4px; max-height:4px; border-radius:2px; }
QProgressBar#metricProgress::chunk { border-radius:2px; }

/* Reconciliation keeps the accepted geometry but restores mockup type weight. */
QLabel#automationReconLabel { font-size:10px; font-weight:500; }
QLabel#automationReconValue { font-size:14px; font-weight:750; }

/* Source summary: clear two-level identity on the left and one aligned toolbar
   on the right; table begins immediately below it. */
QFrame#automationSourcePanel { border-color:#DCE4EF; }
QLabel#automationSourceIcon {
    background:#EEF3FF;
    border-radius:6px;
    padding:2px;
}
QLabel#automationSourceHint { color:#73849A; font-size:9px; padding-left:25px; }
QFrame#automationSourcePanel QComboBox#sourceCompactFilter,
QFrame#automationSourcePanel QLineEdit#sourceCompactSearch,
QFrame#automationSourcePanel QPushButton#automationCompactButton {
    min-height:24px;
    max-height:26px;
    font-size:10px;
}
QTableWidget#dashboardSourceTable { font-size:11px; color:#263B59; }
QTableWidget#dashboardSourceTable QHeaderView::section {
    background:#F5F8FC;
    color:#3E5573;
    font-size:10px;
    font-weight:700;
    min-height:21px;
}

/* Current distribution: this is now a bank-by-bank analytical surface rather
   than a decorative mini-table. */
QFrame#automationPreviousPanel {
    background:#FFFFFF;
    border:1px solid #D8E2EF;
    border-radius:9px;
}
QLabel#automationBreakdownIcon {
    background:#EEF3FF;
    border-radius:6px;
    padding:2px;
}
QLabel#automationBreakdownFilterLabel {
    color:#718096;
    font-size:8px;
    font-weight:600;
    padding-left:2px;
}
QComboBox#breakdownFilter {
    min-height:24px;
    max-height:26px;
    font-size:10px;
    color:#314A6B;
    border-color:#D6E0EC;
}
QLabel#automationBreakdownContext {
    color:#516A8A;
    font-size:9px;
    font-weight:600;
    padding:1px 2px 0 2px;
}
QLabel#automationBreakdownNote {
    color:#8290A3;
    font-size:8px;
    padding:0 2px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    font-size:10px;
    color:#253D5D;
    gridline-color:#E6ECF3;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    background:#F4F7FB;
    color:#516782;
    font-size:9px;
    font-weight:700;
    min-height:20px;
}
QProgressBar#breakdownShare {
    min-height:13px;
    max-height:13px;
    color:#315080;
    background:#EDF1F6;
    border:none;
    border-radius:6px;
    text-align:center;
    font-size:8px;
    font-weight:700;
}
QProgressBar#breakdownShare::chunk {
    background:#7FA1F7;
    border-radius:6px;
}

/* Review section: stronger hierarchy and semantic attention marker without
   changing queue logic or inspector typography. */
QLabel#automationReviewIcon {
    color:#FFFFFF;
    background:#EF4764;
    border-radius:10px;
    font-size:12px;
    font-weight:800;
}
QLabel#automationSectionTitle { font-size:14px; font-weight:750; color:#111827; }
QPushButton#automationViewTab {
    min-height:25px;
    padding:3px 9px;
    border-radius:6px;
    font-size:11px;
    font-weight:600;
}
QPushButton#automationViewTab[tone="warning"] { color:#9A6500; }
QPushButton#automationViewTab[tone="success"] { color:#087A4B; }
QPushButton#automationViewTab[tone="neutral"] { color:#526986; }
QPushButton#automationViewTab:checked {
    color:#315BE8;
    background:#EEF3FF;
    border-bottom:2px solid #315BE8;
    font-weight:700;
}
QLineEdit#automationSearch, QComboBox#automationFilter, QPushButton#automationToolbarButton {
    min-height:25px;
    font-size:11px;
}
QTableWidget#attentionTable { font-size:11px; color:#233A58; }
QTableWidget#attentionTable QHeaderView::section {
    background:#F3F6FA;
    color:#3C526E;
    font-size:10px;
    font-weight:700;
    min-height:22px;
}
QLabel#recordStatusPill { font-size:10px; font-weight:700; }
"""

# 2026-09-18 manual parity pass 7A — finish width regressions and center typography.
MAIN_STYLE += """
/* ===== Pass 7A: KPI width + source fit + center type + review count chips ===== */
/* The dashboard hierarchy is intentionally a touch stronger than inspector
   typography.  The inspector was already accepted and remains untouched. */
QLabel#automationMetricLabel {
    color:#4D627E;
    font-size:12px;
    font-weight:600;
}
QLabel#automationMetricValue {
    color:#0B1324;
    font-size:16px;
    font-weight:800;
}
QLabel#automationMetricDetail {
    color:#6A7C94;
    font-size:10px;
    font-weight:500;
}
QLabel#automationReconLabel {
    color:#60738D;
    font-size:11px;
    font-weight:550;
}
QLabel#automationReconValue {
    color:#0F172A;
    font-size:15px;
    font-weight:800;
}

/* Source summary now has enough filename room without re-growing the card. */
QLabel#automationCompactTitle {
    color:#111827;
    font-size:13px;
    font-weight:750;
}
QLabel#automationCompactBadge {
    font-size:9px;
    font-weight:700;
}
QLabel#automationSourceHint {
    color:#6D8099;
    font-size:10px;
    font-weight:500;
}
QFrame#automationSourcePanel QComboBox#sourceCompactFilter,
QFrame#automationSourcePanel QLineEdit#sourceCompactSearch,
QFrame#automationSourcePanel QPushButton#automationCompactButton {
    min-height:25px;
    max-height:27px;
    font-size:11px;
    font-weight:500;
}
QTableWidget#dashboardSourceTable {
    color:#223955;
    font-size:11px;
}
QTableWidget#dashboardSourceTable QHeaderView::section {
    background:#F3F7FB;
    color:#354D6C;
    font-size:11px;
    font-weight:750;
    min-height:22px;
    padding:2px 3px;
}

/* Analytical breakdown keeps the finished Pass-6 structure; this pass only
   makes its hierarchy match the target typography. */
QLabel#automationBreakdownFilterLabel {
    color:#647892;
    font-size:9px;
    font-weight:650;
}
QComboBox#breakdownFilter {
    min-height:25px;
    max-height:27px;
    font-size:11px;
    font-weight:500;
}
QLabel#automationBreakdownContext {
    color:#486383;
    font-size:10px;
    font-weight:650;
}
QLabel#automationBreakdownNote {
    color:#788AA1;
    font-size:9px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    color:#213A59;
    font-size:11px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    color:#425B79;
    font-size:10px;
    font-weight:750;
    min-height:21px;
}

/* Review counts read as intentional semantic chips rather than loose text.
   Checked state remains the primary blue selection language used elsewhere. */
QPushButton#automationViewTab {
    min-height:24px;
    padding:3px 9px;
    border:1px solid #E1E7EF;
    border-radius:12px;
    font-size:11px;
    font-weight:650;
}
QPushButton#automationViewTab[tone="warning"] {
    color:#946200;
    background:#FFF7E3;
    border-color:#F3E1AE;
}
QPushButton#automationViewTab[tone="success"] {
    color:#08764A;
    background:#ECF9F2;
    border-color:#CFEEDD;
}
QPushButton#automationViewTab[tone="neutral"] {
    color:#526985;
    background:#F5F7FA;
    border-color:#E2E7EE;
}
QPushButton#automationViewTab:hover {
    color:#274FD9;
    background:#F1F5FF;
    border-color:#CED9F7;
}
QPushButton#automationViewTab:checked {
    color:#254FD8;
    background:#EAF0FF;
    border:1px solid #BFD0FF;
    font-weight:750;
}
QLineEdit#automationSearch,
QComboBox#automationFilter,
QPushButton#automationToolbarButton {
    min-height:26px;
    font-size:11px;
    font-weight:500;
}
QTableWidget#attentionTable {
    color:#213954;
    font-size:11px;
}
QTableWidget#attentionTable QHeaderView::section {
    background:#F1F5F9;
    color:#344B68;
    font-size:11px;
    font-weight:750;
    min-height:23px;
}
QLabel#recordStatusPill {
    font-size:10px;
    font-weight:750;
}
"""


# 2026-09-18 manual parity pass 8 — premium colour tints, condensed source summary, bank badges.
MAIN_STYLE += """
/* ===== Pass 8: colour depth + compact source summary + bank badges ===== */
/* Premium colour language: keep the clean white workspace, but let the KPI
   cards carry a subtle semantic tint so success/warning/manual/error states
   are readable at a glance. */
QFrame#automationMetricTile[tone="success"] {
    background:#F2FBF7;
    border:1px solid #CFECDD;
}
QFrame#automationMetricTile[tone="critical"] {
    background:#FFF4F6;
    border:1px solid #F4D7DE;
}
QFrame#automationMetricTile[tone="warning"] {
    background:#FFF8E8;
    border:1px solid #F1DEAE;
}
QFrame#automationMetricTile[tone="manual"] {
    background:#FFF5EC;
    border:1px solid #F3D9BF;
}
QFrame#automationMetricTile[tone="info"] {
    background:#F2F6FF;
    border:1px solid #D7E2FF;
}
QLabel#automationMetricIcon[tone="success"] { background:#DDF7EA; color:#0C9B68; }
QLabel#automationMetricIcon[tone="critical"] { background:#FFE3EA; color:#D94769; }
QLabel#automationMetricIcon[tone="warning"] { background:#FFF0C8; color:#C88A00; }
QLabel#automationMetricIcon[tone="manual"] { background:#FFE6CF; color:#D87A1A; }
QLabel#automationMetricIcon[tone="info"] { background:#E2EBFF; color:#4A6DE6; }
QLabel#automationMetricLabel { color:#4A607C; font-size:12px; font-weight:650; }
QLabel#automationMetricValue { color:#0B1324; font-size:17px; font-weight:820; }
QLabel#automationMetricDetail { color:#5F728D; font-size:10px; font-weight:560; }
QProgressBar#metricProgress { background:#E6ECF4; }
QProgressBar#metricProgress[tone="success"]::chunk { background:#15B26B; }
QProgressBar#metricProgress[tone="warning"]::chunk { background:#E2A300; }
QProgressBar#metricProgress[tone="manual"]::chunk { background:#E8892F; }
QProgressBar#metricProgress[tone="critical"]::chunk { background:#E05278; }
QProgressBar#metricProgress[tone="info"]::chunk { background:#4F75EE; }

/* Reconciliation strip keeps its proven geometry but receives a more premium
   soft-surface treatment. */
QFrame#automationReconciliationStrip {
    background:#FFFFFF;
    border:1px solid #DEE6F0;
    border-radius:9px;
}
QFrame#automationReconCell {
    background:#FAFCFF;
    border:none;
    border-right:1px solid #E5EBF3;
    border-radius:0;
}
QFrame#automationReconCell[tone="success"] {
    background:#EEF9F4;
    border:1px solid #D7EEDF;
    border-radius:8px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF8E7;
    border:1px solid #F2DEAB;
    border-radius:8px;
}
QLabel#automationReconTitle { color:#111827; font-size:13px; font-weight:760; }
QLabel#automationReconLabel { color:#60738D; font-size:11px; font-weight:560; }
QLabel#automationReconValue { color:#0F172A; font-size:15px; font-weight:800; }

/* Source summary: remove filename noise from the dashboard view so the real
   accounting facts can breathe. */
QFrame#automationSourcePanel {
    background:#FFFFFF;
    border:1px solid #DCE4EF;
    border-radius:9px;
}
QTableWidget#dashboardSourceTable {
    color:#213852;
    font-size:11px;
}
QTableWidget#dashboardSourceTable QHeaderView::section {
    background:#F4F7FB;
    color:#3A5170;
    font-size:10px;
    font-weight:760;
    min-height:22px;
    padding:2px 2px;
}

/* Bank rows in the breakdown use small branded badge markers. */
QWidget#automationBankCell { background:transparent; }
QLabel#automationBankName { background:transparent; }

/* Breakdown gets a touch more depth to match the source card. */
QFrame#automationPreviousPanel {
    background:#FFFFFF;
    border:1px solid #D9E3F0;
    border-radius:9px;
}
QLabel#automationBreakdownTotal {
    background:#EDF3FF;
    color:#244CA9;
    border:1px solid #D5E2FF;
    border-radius:10px;
    padding:4px 10px;
    font-size:12px;
    font-weight:780;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    background:#F4F7FB;
    color:#415A7B;
    font-size:10px;
    font-weight:760;
    min-height:21px;
}
QProgressBar#breakdownShare {
    min-height:14px;
    max-height:14px;
    background:#E9EEF6;
    color:#2D4C82;
    font-size:8px;
    font-weight:760;
}
QProgressBar#breakdownShare::chunk {
    background:#89A8F8;
}
"""


# 2026-09-18 manual parity pass 9 — final responsive colour and bank-brand polish.
MAIN_STYLE += """
/* ===== Pass 9: final premium polish ===== */
/* Make the semantic cards unmistakable without turning the workspace into a
   saturated marketing dashboard. Each family gets its own hue, border and
   icon strength. */
QFrame#automationMetricTile[tone="success"] {
    background:#EAF8F1;
    border:1px solid #9FD9BB;
}
QFrame#automationMetricTile[tone="info"] {
    background:#EDF3FF;
    border:1px solid #B4C8FF;
}
QFrame#automationMetricTile[tone="warning"] {
    background:#FFF4CF;
    border:1px solid #EBC66D;
}
QFrame#automationMetricTile[tone="manual"] {
    background:#FFF0E2;
    border:1px solid #EDB475;
}
QFrame#automationMetricTile[tone="critical"] {
    background:#FDECEF;
    border:1px solid #EEA6B5;
}
QLabel#automationMetricIcon {
    min-width:24px;
    max-width:26px;
    min-height:24px;
    max-height:26px;
    border-radius:13px;
    font-size:16px;
    font-weight:800;
}
QLabel#automationMetricIcon[tone="success"] { background:#CFF1DF; color:#078C59; }
QLabel#automationMetricIcon[tone="info"] { background:#D9E5FF; color:#315EDB; }
QLabel#automationMetricIcon[tone="warning"] { background:#FFE5A3; color:#B77800; }
QLabel#automationMetricIcon[tone="manual"] { background:#FFD8B5; color:#D9680F; }
QLabel#automationMetricIcon[tone="critical"] { background:#F9CCD5; color:#CE3655; }
QLabel#automationMetricLabel {
    color:#344A66;
    font-size:11px;
    font-weight:700;
}
QLabel#automationMetricValue {
    color:#081322;
    font-size:16px;
    font-weight:850;
}
QLabel#automationMetricValue[dense="true"] {
    font-size:14px;
    font-weight:850;
}
QLabel#automationMetricLabel[dense="true"] {
    font-size:10px;
    font-weight:700;
}
QLabel#automationMetricDetail {
    color:#526984;
    font-size:9px;
    font-weight:600;
}
QLabel#automationMetricDetail[dense="true"] { font-size:8px; }
QProgressBar#metricProgress { background:#DDE6F1; border-radius:2px; }
QProgressBar#metricProgress[tone="success"]::chunk { background:#08A866; }
QProgressBar#metricProgress[tone="info"]::chunk { background:#4168E8; }
QProgressBar#metricProgress[tone="warning"]::chunk { background:#DA9700; }
QProgressBar#metricProgress[tone="manual"]::chunk { background:#E57418; }
QProgressBar#metricProgress[tone="critical"]::chunk { background:#D94362; }

/* Reconciliation stays calmer than KPI cards, with a stronger verified-fark
   surface so the colour hierarchy remains intentional. */
QFrame#automationReconciliationStrip {
    background:#FFFFFF;
    border:1px solid #D7E1ED;
    border-radius:9px;
}
QFrame#automationReconCell {
    background:#F8FAFD;
    border:none;
    border-right:1px solid #DEE6F0;
}
QFrame#automationReconCell[tone="success"] {
    background:#E7F7EF;
    border:1px solid #A9DFC3;
    border-radius:8px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF2CE;
    border:1px solid #EAC56C;
    border-radius:8px;
}

/* Source summary: compact bank text and right-aligned monetary columns remain
   readable while the inspector is open. */
QTableWidget#dashboardSourceTable {
    background:#FFFFFF;
    alternate-background-color:#FFFFFF;
    color:#1E344F;
    font-size:10px;
    gridline-color:#E0E7F0;
}
QTableWidget#dashboardSourceTable QHeaderView::section {
    background:#EDF3F9;
    color:#2E4766;
    font-size:10px;
    font-weight:800;
    min-height:22px;
    padding:2px 2px;
    border-color:#DBE4EE;
}

/* Bank identity: the first column contains a vector logo mark plus a clean
   bank name, never a second painted item underneath it. */
QWidget#automationBankCell { background:#FFFFFF; }
QLabel#automationBankName {
    color:#213A59;
    background:transparent;
    font-size:11px;
    font-weight:750;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    background:#FFFFFF;
    color:#1F3855;
    font-size:10px;
    gridline-color:#E1E8F1;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    background:#EDF3F9;
    color:#334D6D;
    font-size:10px;
    font-weight:800;
    min-height:22px;
}
QProgressBar#breakdownShare {
    background:#E8EDF5;
    color:#284774;
    border:none;
    border-radius:6px;
    min-height:14px;
    max-height:14px;
    font-size:8px;
    font-weight:800;
}
QProgressBar#breakdownShare::chunk {
    background:#6F91F2;
    border-radius:6px;
}

/* Inspector semantics: missing evidence is visibly neutral, not green. */
QLabel#inspectorEvidenceIcon[tone="success"] { background:#0FA76A; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="warning"] { background:#E49A08; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="critical"] { background:#D83B59; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="info"] { background:#3E67DE; color:#FFFFFF; }
QLabel#inspectorEvidenceIcon[tone="neutral"] { background:#A5AFBD; color:#FFFFFF; }
"""

# 2026-09-18 manual parity pass 10 — neutral premium cards + original bank wordmarks.
MAIN_STYLE += """
/* ===== Pass 10: neutral premium finance surface ===== */
/* White cards carry one restrained semantic accent.  This avoids the rainbow
   look of Pass 9 while keeping state recognition instant and professional. */
QFrame#automationMetricTile,
QFrame#automationMetricTile[tone="success"],
QFrame#automationMetricTile[tone="outflow"],
QFrame#automationMetricTile[tone="info"],
QFrame#automationMetricTile[tone="warning"],
QFrame#automationMetricTile[tone="manual"],
QFrame#automationMetricTile[tone="critical"] {
    background:#FFFFFF;
    border:1px solid #DCE5F0;
    border-radius:10px;
}
QFrame#automationMetricTile[tone="success"] { border-left:3px solid #12A66A; }
QFrame#automationMetricTile[tone="outflow"] { border-left:3px solid #7A4CE0; }
QFrame#automationMetricTile[tone="info"] { border-left:3px solid #3568E8; }
QFrame#automationMetricTile[tone="warning"] { border-left:3px solid #D89B00; }
QFrame#automationMetricTile[tone="manual"] { border-left:3px solid #E57924; }
QFrame#automationMetricTile[tone="critical"] { border-left:3px solid #DF4661; }

QLabel#automationMetricIcon {
    min-width:26px; max-width:26px;
    min-height:26px; max-height:26px;
    border-radius:13px;
    font-size:16px;
    font-weight:800;
}
QLabel#automationMetricIcon[tone="success"] { background:#E2F7ED; color:#0B9B62; }
QLabel#automationMetricIcon[tone="outflow"] { background:#F0EAFE; color:#6D43CF; }
QLabel#automationMetricIcon[tone="info"] { background:#E8EFFF; color:#315FE0; }
QLabel#automationMetricIcon[tone="warning"] { background:#FFF2CB; color:#B97A00; }
QLabel#automationMetricIcon[tone="manual"] { background:#FFE9D6; color:#D96A17; }
QLabel#automationMetricIcon[tone="critical"] { background:#FDE3E8; color:#D33C59; }
QLabel#automationMetricLabel { color:#425773; font-size:11px; font-weight:700; }
QLabel#automationMetricValue { color:#0B1423; font-size:16px; font-weight:850; }
QLabel#automationMetricDetail { color:#6D7F96; font-size:9px; font-weight:550; }
QLabel#automationMetricValue[dense="true"] { font-size:14px; }
QLabel#automationMetricLabel[dense="true"] { font-size:10px; }
QLabel#automationMetricDetail[dense="true"] { font-size:8px; }
QProgressBar#metricProgress { background:#E8EDF4; border:none; border-radius:2px; }
QProgressBar#metricProgress[tone="success"]::chunk { background:#12A66A; }
QProgressBar#metricProgress[tone="warning"]::chunk { background:#D89B00; }
QProgressBar#metricProgress[tone="manual"]::chunk { background:#E57924; }
QProgressBar#metricProgress[tone="critical"]::chunk { background:#DF4661; }

/* Reconciliation is a financial statement, not a status dashboard. */
QFrame#automationReconciliationStrip {
    background:#FFFFFF;
    border:1px solid #DCE5EF;
    border-radius:9px;
}
QFrame#automationReconCell {
    background:#FFFFFF;
    border:none;
    border-right:1px solid #E4EAF1;
    border-radius:0;
}
QFrame#automationReconCell[tone="success"] {
    background:#EFF9F4;
    border:1px solid #CBE8D8;
    border-radius:8px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF7E5;
    border:1px solid #EDD8A6;
    border-radius:8px;
}
QLabel#automationReconLabel { color:#60738D; font-size:11px; font-weight:550; }
QLabel#automationReconValue { color:#0F172A; font-size:15px; font-weight:800; }

/* Bank wordmarks are real bundled assets; keep their cell clean and roomy. */
QWidget#automationBankCell { background:#FFFFFF; }
QLabel#automationBankMark { background:transparent; border:none; padding:0; }
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    background:#FFFFFF;
    color:#213A59;
    font-size:11px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    background:#F4F7FB;
    color:#425A78;
    font-size:10px;
    font-weight:750;
    min-height:22px;
}
QProgressBar#breakdownShare {
    background:#E9EEF6;
    color:#2E4C7A;
    border:none;
    border-radius:6px;
    min-height:13px;
    max-height:13px;
}
QProgressBar#breakdownShare::chunk { background:#6F91EF; border-radius:6px; }
"""

# 2026-09-19 manual parity pass 11 — vivid filled KPI badges, compact logo-only banks.
MAIN_STYLE += """
/* ===== Pass 11: vivid KPI badges + compact real-bank logos ===== */
QFrame#automationMetricTile,
QFrame#automationMetricTile[tone="success"],
QFrame#automationMetricTile[tone="outflow"],
QFrame#automationMetricTile[tone="info"],
QFrame#automationMetricTile[tone="warning"],
QFrame#automationMetricTile[tone="manual"],
QFrame#automationMetricTile[tone="critical"] {
    background:#FFFFFF;
    border:1px solid #DCE5F0;
    border-radius:10px;
}
QFrame#automationMetricTile[tone="success"] { border-left:4px solid #17B26A; }
QFrame#automationMetricTile[tone="outflow"] { border-left:4px solid #FF5478; }
QFrame#automationMetricTile[tone="info"] { border-left:4px solid #4E7CFF; }
QFrame#automationMetricTile[tone="warning"] { border-left:4px solid #F4B400; }
QFrame#automationMetricTile[tone="manual"] { border-left:4px solid #FF8A2A; }
QFrame#automationMetricTile[tone="critical"] { border-left:4px solid #F0445A; }

QLabel#automationMetricIcon {
    color:#FFFFFF;
    border:none;
    font-weight:900;
    qproperty-alignment: 'AlignCenter';
}
QLabel#automationMetricIcon[variant="finance"] {
    min-width:30px; max-width:30px;
    min-height:30px; max-height:30px;
    border-radius:15px;
    font-size:19px;
}
QLabel#automationMetricIcon[variant="status"] {
    min-width:24px; max-width:24px;
    min-height:24px; max-height:24px;
    border-radius:12px;
    font-size:14px;
}
QLabel#automationMetricIcon[tone="success"] { background:#17B26A; color:#FFFFFF; }
QLabel#automationMetricIcon[tone="outflow"] { background:#FF5478; color:#FFFFFF; }
QLabel#automationMetricIcon[tone="info"] { background:#4E7CFF; color:#FFFFFF; }
QLabel#automationMetricIcon[tone="warning"] { background:#F4B400; color:#FFFFFF; }
QLabel#automationMetricIcon[tone="manual"] { background:#FF8A2A; color:#FFFFFF; }
QLabel#automationMetricIcon[tone="critical"] { background:#F0445A; color:#FFFFFF; }

QLabel#automationMetricLabel {
    color:#516276;
    font-size:11px;
    font-weight:650;
}
QLabel#automationMetricValue {
    color:#111827;
    font-size:16px;
    font-weight:820;
}
QLabel#automationMetricDetail {
    color:#6B7C93;
    font-size:10px;
    font-weight:560;
}
QLabel#automationMetricValue[dense="true"] { font-size:14px; }
QLabel#automationMetricLabel[dense="true"] { font-size:10px; }
QLabel#automationMetricDetail[dense="true"] { font-size:8px; }

QProgressBar#metricProgress {
    background:#E7EDF5;
    border:none;
    border-radius:2px;
}
QProgressBar#metricProgress[tone="success"]::chunk { background:#17B26A; }
QProgressBar#metricProgress[tone="warning"]::chunk { background:#F4B400; }
QProgressBar#metricProgress[tone="manual"]::chunk { background:#FF8A2A; }
QProgressBar#metricProgress[tone="critical"]::chunk { background:#F0445A; }

/* Reconciliation summary deserves a larger, more premium financial presence. */
QFrame#automationReconciliationStrip {
    background:#FFFFFF;
    border:1px solid #DCE5EF;
    border-radius:10px;
    min-height:72px;
}
QFrame#automationReconCell {
    background:#FFFFFF;
    border:none;
    border-right:1px solid #E4EAF1;
    border-radius:0;
}
QFrame#automationReconCell[tone="success"] {
    background:#EFFAF4;
    border:1px solid #CCE8D8;
    border-radius:8px;
}
QFrame#automationReconCell[tone="warning"] {
    background:#FFF7E7;
    border:1px solid #EDD49E;
    border-radius:8px;
}
QLabel#automationReconTitle { color:#172033; font-size:14px; font-weight:760; }
QLabel#automationReconLabel { color:#5F738E; font-size:12px; font-weight:560; }
QLabel#automationReconValue { color:#101828; font-size:16px; font-weight:820; }

/* Breakdown bank column now shows only the official compact logo mark. */
QWidget#automationBankCell { background:#FFFFFF; }
QLabel#automationBankMark {
    background:transparent;
    border:none;
    padding:0;
    min-width:20px;
    max-width:22px;
    min-height:20px;
    max-height:22px;
}
"""

# 2026-09-19 manual pass 12 — lighter premium typography and finance-card parity.
MAIN_STYLE += """
/* ===== Pass 12: softer finance KPIs, thinner typography, clearer bank symbols ===== */
QFrame#automationMetricTile[variant="finance"] {
    background:#FFFFFF;
    border:1px solid #D7DFEA;
    border-left:none;
    border-radius:10px;
}
QFrame#automationMetricTile[variant="status"] {
    background:#FFFFFF;
    border:1px solid #DCE5F0;
    border-radius:10px;
}
/* Keep left accent only for status cards; finance cards follow the reference card look. */
QFrame#automationMetricTile[variant="status"][tone="success"] { border-left:4px solid #17B26A; }
QFrame#automationMetricTile[variant="status"][tone="warning"] { border-left:4px solid #F4B400; }
QFrame#automationMetricTile[variant="status"][tone="manual"] { border-left:4px solid #FF8A2A; }
QFrame#automationMetricTile[variant="status"][tone="critical"] { border-left:4px solid #F0445A; }

QLabel#automationMetricIcon[variant="finance"] {
    min-width:28px; max-width:28px;
    min-height:28px; max-height:28px;
    border-radius:14px;
    font-size:17px;
    font-weight:700;
}
QLabel#automationMetricIcon[variant="status"] {
    min-width:23px; max-width:23px;
    min-height:23px; max-height:23px;
    border-radius:11px;
    font-size:13px;
    font-weight:700;
}
/* First three KPI cards match the reference more closely: softer filled discs. */
QLabel#automationMetricIcon[variant="finance"][tone="success"] { background:#DDF7EA; color:#16A34A; }
QLabel#automationMetricIcon[variant="finance"][tone="outflow"] { background:#FFE3EA; color:#F24870; }
QLabel#automationMetricIcon[variant="finance"][tone="info"] { background:#E2EAFF; color:#3B6FF5; }
/* Status cards stay vivid, solid, and legible. */
QLabel#automationMetricIcon[variant="status"][tone="success"] { background:#17B26A; color:#FFFFFF; }
QLabel#automationMetricIcon[variant="status"][tone="warning"] { background:#F4B400; color:#FFFFFF; }
QLabel#automationMetricIcon[variant="status"][tone="manual"] { background:#FF8A2A; color:#FFFFFF; }
QLabel#automationMetricIcon[variant="status"][tone="critical"] { background:#F0445A; color:#FFFFFF; }

QLabel#automationMetricLabel {
    color:#53657D;
    font-size:11px;
    font-weight:560;
}
QLabel#automationMetricValue {
    color:#0F172A;
    font-size:15px;
    font-weight:720;
}
QLabel#automationMetricDetail {
    color:#6B7C93;
    font-size:10px;
    font-weight:500;
}
QLabel#automationMetricValue[dense="true"] { font-size:13px; }
QLabel#automationMetricLabel[dense="true"] { font-size:10px; }
QLabel#automationMetricDetail[dense="true"] { font-size:8px; }

QLabel#automationReconTitle { color:#172033; font-size:14px; font-weight:740; }
QLabel#automationReconLabel { color:#5F738E; font-size:12px; font-weight:520; }
QLabel#automationReconValue { color:#101828; font-size:15px; font-weight:730; }
QFrame#automationReconciliationStrip { min-height:74px; }
QFrame#automationReconCell[tone="success"] { background:#EFFAF4; }
QFrame#automationReconCell[tone="warning"] { background:#FFF7E7; }

QLabel#automationBankMark {
    min-width:26px;
    max-width:28px;
    min-height:26px;
    max-height:28px;
}
"""

# 2026-09-19 manual pass 13 — UI-only stability polish.
MAIN_STYLE += """
/* ===== Pass 13: visible bank marks + inspector-width source readability ===== */
QLabel#automationBankMark {
    background:#FFFFFF;
    border:none;
    padding:0;
    min-width:28px;
    max-width:30px;
    min-height:28px;
    max-height:30px;
}
QWidget#automationBankCell { background:#FFFFFF; }

/* Source summary stays readable with the inspector open.  Receipt-detail
   columns collapse responsively in Python; the remaining cells use compact,
   finance-first typography rather than ellipsizing every amount. */
QTableWidget#dashboardSourceTable {
    font-size:10px;
    color:#243B59;
}
QTableWidget#dashboardSourceTable QHeaderView::section {
    font-size:9px;
    font-weight:650;
    color:#405875;
    padding-left:3px;
    padding-right:3px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    font-size:10px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    font-size:9px;
    font-weight:650;
}

/* Final typography trim: premium finance UI should be strong, not heavy. */
QLabel#automationMetricLabel { font-weight:540; }
QLabel#automationMetricValue { font-weight:700; }
QLabel#automationReconTitle { font-weight:700; }
QLabel#automationReconLabel { font-weight:500; }
QLabel#automationReconValue { font-weight:700; }
"""


# 2026-09-19 manual pass 14 — exact approved KPI reference + bank-first breakdown.
MAIN_STYLE += """
/* ===== Pass 14: exact first-three KPI reference ===== */
QFrame#automationMetricTile[variant="finance"] {
    background:#F8FAFC;
    border:1px solid #E7ECF2;
    border-radius:11px;
}
QLabel#automationMetricIcon[variant="finance"] {
    min-width:34px; max-width:34px;
    min-height:34px; max-height:34px;
    border-radius:17px;
    border:none;
    padding:0;
}
/* sampled directly from the approved mockup */
QLabel#automationMetricIcon[variant="finance"][tone="success"] { background:#DAF4E9; color:#23936F; }
QLabel#automationMetricIcon[variant="finance"][tone="outflow"] { background:#FFE7EA; color:#E25B72; }
QLabel#automationMetricIcon[variant="finance"][tone="info"] { background:#E2EAFF; color:#5877D9; }
QLabel#automationMetricLabel[variant="finance"] {
    color:#60738A;
    font-size:11px;
    font-weight:500;
}
QLabel#automationMetricValue[variant="finance"] {
    color:#101820;
    font-size:16px;
    font-weight:700;
}
QLabel#automationMetricDetail[variant="finance"] {
    color:#7A8A9D;
    font-size:9px;
    font-weight:400;
}
QLabel#automationMetricLabel[variant="finance"][dense="true"] { font-size:10px; font-weight:500; }
QLabel#automationMetricValue[variant="finance"][dense="true"] { font-size:14px; font-weight:700; }
QLabel#automationMetricDetail[variant="finance"][dense="true"] { font-size:8px; font-weight:400; }

/* ===== Pass 14: bank-first operation breakdown ===== */
QWidget#automationBankCell { background:#FFFFFF; }
QLabel#automationBankMark {
    background:transparent;
    min-width:24px; max-width:26px;
    min-height:24px; max-height:26px;
}
QLabel#automationBankName {
    color:#243B59;
    font-size:11px;
    font-weight:650;
    padding:0;
}
QProgressBar#breakdownShare {
    min-height:11px; max-height:11px;
}
"""

# 2026-09-19 manual pass 15 — exact finance badge tones + readable bank distribution.
MAIN_STYLE += """
/* ===== Pass 15: approved first-three KPI parity ===== */
QFrame#automationMetricTile[variant="finance"] {
    background:#FFFFFF;
    border:1px solid #E6EBF1;
    border-radius:11px;
}
/* Finance icon circles are painted by _FinanceMetricBadge for guaranteed
   round geometry; keep QSS transparent so Qt cannot square the badge. */
QLabel#automationMetricIcon[variant="finance"] {
    background:transparent;
    border:none;
    padding:0;
    min-width:34px; max-width:34px;
    min-height:34px; max-height:34px;
}
QLabel#automationMetricLabel[variant="finance"] {
    color:#60738A;
    font-size:11px;
    font-weight:500;
}
QLabel#automationMetricValue[variant="finance"] {
    color:#101820;
    font-size:16px;
    font-weight:690;
}
QLabel#automationMetricDetail[variant="finance"] {
    color:#7A8A9D;
    font-size:9px;
    font-weight:400;
}

/* Bank distribution: readable bank identity without sacrificing full amount. */
QLabel#automationBankName {
    color:#1F3653;
    font-size:11px;
    font-weight:650;
    padding:0;
}
QLabel#automationBankMark {
    min-width:26px; max-width:28px;
    min-height:26px; max-height:28px;
}
QTableWidget#operationBreakdownTable QHeaderView::section {
    padding-left:3px;
    padding-right:3px;
}
QProgressBar#breakdownShare {
    min-height:10px;
    max-height:10px;
}
"""

# 2026-09-20 manual pass 16 — inspector lower-detail readability.
MAIN_STYLE += """
/* ===== Pass 16: detail-card lower texts are easier to read ===== */
QLabel#inspectorKey {
    color:#6B7C93;
    font-size:11px;
    font-weight:560;
}
QLabel#inspectorValue {
    color:#294D85;
    font-size:11px;
    font-weight:600;
}
QLabel#inspectorValue[emphasis="true"] {
    color:#173F8A;
    font-size:12px;
    font-weight:700;
}
QFrame#inspectorEvidenceRow {
    min-height:28px;
}
QLabel#inspectorWarning {
    font-size:10px;
    padding:8px 9px;
}
"""


# Pass 17 V2: exact supplied mockup KPI trio.
MAIN_STYLE += """
QFrame#automationMetricTile[variant="finance"] {
    background:#F8FAFC;
    border:1px solid #EDF1F5;
    border-radius:11px;
}
QLabel#automationMetricIcon[variant="finance"] {
    background:transparent;
    border:none;
    padding:0;
    min-width:38px; max-width:38px;
    min-height:38px; max-height:38px;
}
QLabel#automationMetricLabel[variant="finance"] {
    color:#5F7189;
    font-size:12px;
    font-weight:500;
}
QLabel#automationMetricValue[variant="finance"] {
    color:#0B111B;
    font-size:18px;
    font-weight:700;
}
QLabel#automationMetricDetail[variant="finance"] {
    color:#72839A;
    font-size:10px;
    font-weight:500;
}
QLabel#automationMetricLabel[variant="finance"][dense="true"] {
    font-size:11px;
    font-weight:500;
}
QLabel#automationMetricValue[variant="finance"][dense="true"] {
    font-size:16px;
    font-weight:700;
}
QLabel#automationMetricDetail[variant="finance"][dense="true"] {
    font-size:9px;
    font-weight:500;
}
"""


# Pass 18: first-three KPI exact mockup icon parity.
MAIN_STYLE += """
QFrame#automationMetricTile[variant="finance"] {
    background:#FFFFFF;
    border:1px solid #E9EEF4;
    border-radius:12px;
}
QLabel#automationMetricIcon[variant="finance"] {
    background:transparent;
    border:none;
    padding:0;
    min-width:34px; max-width:34px;
    min-height:34px; max-height:34px;
}
QLabel#automationMetricLabel[variant="finance"] {
    color:#6E7F97;
    font-size:12px;
    font-weight:500;
}
QLabel#automationMetricValue[variant="finance"] {
    color:#101828;
    font-size:17px;
    font-weight:760;
}
QLabel#automationMetricDetail[variant="finance"] {
    color:#7E8DA2;
    font-size:10px;
    font-weight:500;
}
QLabel#automationMetricLabel[variant="finance"][dense="true"] {
    font-size:11px;
}
QLabel#automationMetricValue[variant="finance"][dense="true"] {
    font-size:15px;
    font-weight:740;
}
QLabel#automationMetricDetail[variant="finance"][dense="true"] {
    font-size:9px;
}
"""

# Pass 20: exact mockup raster KPI icons.
MAIN_STYLE += """
QLabel#automationMetricIcon[variant="finance"] {
    background:transparent;
    border:none;
    padding:0;
    min-width:38px; max-width:38px;
    min-height:38px; max-height:38px;
}
"""


# Pass 21: exact native mockup first-three KPI.
MAIN_STYLE += """
QFrame#automationMetricTile[variant="finance"] {
    background:#F8FAFC;
    border:1px solid #E7ECF3;
    border-radius:11px;
}
QLabel#automationMetricIcon[variant="finance"] {
    background:transparent;
    border:none;
    padding:0;
    min-width:38px; max-width:38px;
    min-height:38px; max-height:38px;
}
QLabel#automationMetricLabel[variant="finance"] {
    color:#62758E;
    font-size:11px;
    font-weight:500;
}
QLabel#automationMetricValue[variant="finance"] {
    color:#0B111B;
    font-size:18px;
    font-weight:700;
}
QLabel#automationMetricDetail[variant="finance"] {
    color:#72839A;
    font-size:10px;
    font-weight:500;
}
QLabel#automationMetricLabel[variant="finance"][dense="true"] { font-size:10px; font-weight:500; }
QLabel#automationMetricValue[variant="finance"][dense="true"] { font-size:16px; font-weight:700; }
QLabel#automationMetricDetail[variant="finance"][dense="true"] { font-size:9px; font-weight:500; }
"""


# Pass 22: full mockup visual parity shell.
MAIN_STYLE += """
/* ===== Global shell / exact mockup language ===== */
QFrame#sidebar {
    background:#1C2734;
    border-right:1px solid #293A4C;
}
QFrame#brandArea {
    background:transparent;
    border:none;
    padding:0;
}
QFrame#companyCard {
    background:#1D2937;
    border:1px solid #35475D;
    border-radius:6px;
}
QFrame#companyCard:hover {
    background:#223044;
    border-color:#49617D;
}
QLabel#companyCardName {
    color:#F5F7FB;
    font-size:11px;
    font-weight:700;
}
QLabel#companyCardHint {
    color:#9BAABD;
    font-size:9px;
}
QPushButton#companyCardChevron {
    color:#C5D1E0;
    background:transparent;
    border:none;
    border-radius:4px;
}
QPushButton#companyCardChevron:hover {
    background:#243345;
    color:#FFFFFF;
}
QFrame#sidebarItem {
    background:transparent;
    border:none;
    border-radius:5px;
}
QFrame#sidebarItem[active="true"] {
    background:#26374B;
    border-left:3px solid #5279FF;
}
QPushButton#accountingSubnavButton {
    color:#C9D4E3;
    background:transparent;
    border:none;
    border-radius:4px;
    min-height:27px;
    padding:4px 9px;
    text-align:left;
    font-size:10px;
}
QPushButton#accountingSubnavButton:hover {
    background:#243345;
    color:#FFFFFF;
}
QPushButton#accountingSubnavButton[active="true"] {
    background:#3157C8;
    color:#FFFFFF;
    font-weight:700;
}
QPushButton#sidebarFixedSettings {
    color:#D7E0EC;
    background:transparent;
    border:none;
    border-top:1px solid #2B3B4D;
    min-height:32px;
    text-align:left;
}
QFrame#userCard {
    background:transparent;
    border:none;
    border-top:1px solid #2B3B4D;
}

/* ===== Top bar ===== */
QFrame#workspaceHeader {
    background:#FFFFFF;
    border-bottom:1px solid #E8EDF3;
    min-height:42px;
    max-height:42px;
}
QLabel#workspaceHeading {
    color:#62748D;
    font-size:10px;
    font-weight:500;
}
QLabel#workspaceContext {
    color:#315BE8;
    font-size:10px;
    font-weight:600;
}
QPushButton#topbarTextAction {
    color:#36527F;
    background:transparent;
    border:none;
    min-height:28px;
    padding:4px 8px;
    font-size:10px;
}
QLineEdit#globalSearch {
    background:#FFFFFF;
    color:#243B59;
    border:1px solid #DDE5EF;
    border-radius:7px;
    min-height:28px;
    max-height:28px;
    padding:0 10px;
    font-size:10px;
}
QPushButton#topbarIconAction {
    color:#60738D;
    background:transparent;
    border:none;
    min-width:28px;
    max-width:28px;
    min-height:28px;
    max-height:28px;
}

/* ===== Main workspace ===== */
QWidget#automationCanvas {
    background:#F7F9FC;
}
QLabel#automationPageTitle {
    color:#101828;
    font-size:23px;
    font-weight:760;
}
QLabel#automationPageSubtitle {
    color:#405A83;
    font-size:11px;
    font-weight:500;
}
QLabel#automationTitleIcon { color:#315BE8; }
QFrame#automationSummaryRail {
    background:#FFFFFF;
    border:1px solid #E6ECF3;
    border-radius:9px;
    min-height:54px;
    max-height:58px;
}
QLabel#automationStatIcon { color:#365FCB; }
QLabel#automationStatValue {
    color:#101828;
    font-size:14px;
    font-weight:720;
}
QLabel#automationStatDetail {
    color:#71829B;
    font-size:9px;
    font-weight:500;
}
QPushButton#automationAddSource {
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #5D7DFF;
    border-radius:6px;
    min-height:28px;
    padding:4px 10px;
    font-size:10px;
    font-weight:650;
}

/* ===== Step rail ===== */
QFrame#automationStepRail {
    background:#FFFFFF;
    border:1px solid #EDF1F5;
    border-radius:8px;
    min-height:36px;
    max-height:40px;
}
QLabel#automationStepNumber {
    min-width:21px;
    max-width:21px;
    min-height:21px;
    max-height:21px;
    border-radius:10px;
    font-size:9px;
    font-weight:700;
}
QLabel#automationStepTitle {
    color:#566986;
    font-size:10px;
    font-weight:500;
}
QLabel#automationStepTitle[stepState="active"] {
    color:#315BE8;
    font-weight:700;
}

/* ===== Status KPI cards 4-7; first three are intentionally untouched ===== */
QFrame#automationMetricTile[variant="status"] {
    border:1px solid #EDF1F5;
    border-radius:9px;
    border-left:1px solid #EDF1F5;
}
QFrame#automationMetricTile[variant="status"][tone="success"] {
    background:#F8FCFA;
    border:1px solid #E6F3EC;
}
QFrame#automationMetricTile[variant="status"][tone="warning"] {
    background:#FFFCF6;
    border:1px solid #F6EBCD;
}
QFrame#automationMetricTile[variant="status"][tone="manual"] {
    background:#FFFAF6;
    border:1px solid #F6E6D9;
}
QFrame#automationMetricTile[variant="status"][tone="critical"] {
    background:#FFF9FA;
    border:1px solid #F4E2E6;
}
QLabel#automationMetricIcon[variant="status"] {
    min-width:22px;
    max-width:22px;
    min-height:22px;
    max-height:22px;
    border-radius:11px;
    font-size:12px;
    font-weight:800;
}
QLabel#automationMetricIcon[variant="status"][tone="success"] { background:#17B26A; color:#FFFFFF; }
QLabel#automationMetricIcon[variant="status"][tone="warning"] { background:#F4B400; color:#FFFFFF; }
QLabel#automationMetricIcon[variant="status"][tone="manual"] { background:#FF8A2A; color:#FFFFFF; }
QLabel#automationMetricIcon[variant="status"][tone="critical"] { background:#E82F4E; color:#FFFFFF; }
QLabel#automationMetricLabel[variant="status"] {
    color:#425773;
    font-size:10px;
    font-weight:600;
}
QLabel#automationMetricValue[variant="status"] {
    color:#101828;
    font-size:14px;
    font-weight:760;
}
QLabel#automationMetricDetail[variant="status"] {
    color:#718096;
    font-size:9px;
    font-weight:500;
}
QProgressBar#metricProgress {
    background:#E7EDF5;
    border:none;
    border-radius:3px;
    min-height:5px;
    max-height:5px;
}

/* ===== Reconciliation ===== */
QFrame#automationReconciliationStrip {
    background:#FFFFFF;
    border:1px solid #E5EBF2;
    border-radius:9px;
    min-height:78px;
}
QLabel#automationReconTitle {
    color:#172033;
    font-size:14px;
    font-weight:720;
}
QLabel#automationReconLabel {
    color:#5F738E;
    font-size:11px;
    font-weight:500;
}
QLabel#automationReconValue {
    color:#101828;
    font-size:15px;
    font-weight:720;
}
QFrame#automationReconCell[tone="success"] {
    background:#EEFBF4;
    border:1px solid #D7F1E2;
    border-radius:8px;
}

/* ===== Source + analytical cards ===== */
QFrame#automationSourcePanel,
QFrame#automationPreviousPanel {
    background:#FFFFFF;
    border:1px solid #DDE5EF;
    border-radius:9px;
}
QFrame#automationSourcePanel QTableWidget#dashboardSourceTable,
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    background:#FFFFFF;
    border:none;
    gridline-color:#E2E8F0;
    color:#233A58;
}
QFrame#automationSourcePanel QHeaderView::section,
QFrame#automationPreviousPanel QHeaderView::section {
    background:#F5F8FC;
    color:#405875;
    border:none;
    border-bottom:1px solid #DDE5EF;
    padding:4px 5px;
    font-size:9px;
    font-weight:650;
}
QComboBox#sourceCompactFilter,
QLineEdit#sourceCompactSearch,
QComboBox#breakdownFilter {
    background:#FFFFFF;
    border:1px solid #DDE5EF;
    border-radius:6px;
    min-height:25px;
    padding:2px 8px;
    font-size:10px;
}
QPushButton#automationCompactButton {
    background:#FFFFFF;
    color:#315BE8;
    border:1px solid #D7E1F0;
    border-radius:6px;
    min-height:25px;
    padding:3px 8px;
    font-size:10px;
}

/* ===== Review section ===== */
QWidget#reviewHeadingPanel {
    background:#FFFFFF;
    border:1px solid #E4EAF2;
    border-bottom:none;
    border-radius:8px;
}
QLabel#automationSectionTitle {
    color:#111827;
    font-size:14px;
    font-weight:720;
}
QPushButton#automationViewTab {
    min-height:26px;
    padding:3px 10px;
    border-radius:7px;
    font-size:10px;
    font-weight:600;
}
QTableWidget#attentionTable {
    background:#FFFFFF;
    color:#233A58;
    border:1px solid #E4EAF2;
    font-size:10px;
}
QTableWidget#attentionTable QHeaderView::section {
    background:#F5F8FC;
    color:#3C526E;
    border:none;
    border-bottom:1px solid #DDE5EF;
    min-height:22px;
    padding:4px 5px;
    font-size:9px;
    font-weight:700;
}
QTableWidget#attentionTable::item:selected {
    background:#E9F0FF;
    color:#172033;
}

/* ===== Inspector ===== */
QFrame#inspectorPanel {
    background:#FFFFFF;
    border:1px solid #E1E7EF;
    border-radius:9px;
}
QLabel#inspectorStatusPill {
    border:none;
    border-radius:10px;
    padding:4px 9px;
    font-size:10px;
    font-weight:700;
}
QLabel#inspectorStatusPill[tone="success"] { background:#E5F8ED; color:#087A4B; }
QLabel#inspectorStatusPill[tone="warning"] { background:#FFF0CE; color:#A96500; }
QLabel#inspectorStatusPill[tone="critical"] { background:#FDE5EA; color:#BF1F3B; }
QLabel#inspectorStatusPill[tone="info"] { background:#EAF0FF; color:#315BE8; }
QLabel#inspectorSectionTitle {
    color:#172033;
    font-size:12px;
    font-weight:720;
}
QLabel#inspectorKey {
    color:#687991;
    font-size:11px;
    font-weight:520;
}
QLabel#inspectorValue {
    color:#294D85;
    font-size:11px;
    font-weight:600;
}
QFrame#inspectorEvidenceRow {
    background:#FFFFFF;
    border:none;
    border-bottom:1px solid #EDF1F5;
    min-height:29px;
}
QLabel#inspectorWarning {
    color:#9A610B;
    background:#FFF3D7;
    border:1px solid #F0D198;
    border-radius:6px;
    padding:8px 9px;
    font-size:10px;
}
QFrame#inspectorPanel QPushButton#primary {
    background:#3566EB;
    border:1px solid #3566EB;
    border-radius:6px;
    color:#FFFFFF;
    min-height:40px;
    font-size:11px;
    font-weight:700;
}
QPushButton#inspectorSecondary {
    background:#FFFFFF;
    color:#315080;
    border:1px solid #D9E1EB;
    border-radius:6px;
    min-height:28px;
    font-size:10px;
}
"""


# Pass 23: responsive density + readable financial columns.
MAIN_STYLE += """
/* Middle dashboard cards are deliberately shorter so the operational review
   table remains visible at 900-1080px desktop heights. */
QFrame#automationSourcePanel,
QFrame#automationPreviousPanel {
    padding:0;
}
QTableWidget#dashboardSourceTable {
    font-size:10px;
}
QTableWidget#dashboardSourceTable QHeaderView::section {
    font-size:9px;
    padding-left:2px;
    padding-right:2px;
}
QLabel#automationBreakdownNote {
    font-size:8px;
}
QWidget#reviewHeadingPanel {
    min-height:54px;
    max-height:58px;
}
QTableWidget#attentionTable {
    min-height:116px;
}
/* Wider inspector typography can breathe without shrinking its content. */
QFrame#inspectorPanel {
    padding:0;
}
"""

# Pass 24R2: compact middle dashboard recovery.
MAIN_STYLE += """
/* Source identity rail: exact compact geometry; current code uses automationSourceIcon. */
QFrame#automationSourcePanel QLabel#automationSourceIcon {
    min-width:22px; max-width:22px;
    min-height:22px; max-height:22px;
    padding:0; margin:0;
}
QFrame#automationSourcePanel QLabel#automationCompactBadge {
    min-height:20px; max-height:22px;
    padding:1px 7px;
    border-radius:10px;
}
QFrame#automationSourcePanel QLabel#automationCompactTitle {
    min-height:20px; max-height:22px;
}
QFrame#automationSourcePanel QLabel#automationSourceHint {
    min-height:17px; max-height:19px;
    padding:0; margin:0;
}
QFrame#automationSourcePanel QComboBox#sourceCompactFilter,
QFrame#automationSourcePanel QLineEdit#sourceCompactSearch,
QFrame#automationSourcePanel QPushButton#automationCompactButton {
    min-height:22px; max-height:24px;
}
QFrame#automationSourcePanel,
QFrame#automationPreviousPanel {
    max-height:236px;
}
QWidget#reviewHeadingPanel {
    min-height:42px; max-height:46px;
}
QTableWidget#attentionTable {
    min-height:168px;
}
"""

# Pass 25: measured mockup density parity.
MAIN_STYLE += """
/* Measured against the approved mockup: middle row ~20% shorter. */
QFrame#automationSourcePanel,
QFrame#automationPreviousPanel {
    min-height:184px; max-height:184px;
}
QFrame#automationSourcePanel QLabel#automationCompactTitle,
QFrame#automationPreviousPanel QLabel#automationCompactTitle {
    font-size:10px; min-height:18px; max-height:20px;
}
QFrame#automationSourcePanel QLabel#automationCompactBadge {
    font-size:8px; min-height:18px; max-height:20px; padding:1px 6px;
}
QFrame#automationSourcePanel QLabel#automationSourceHint {
    font-size:8px; min-height:14px; max-height:16px; padding:0; margin:0;
}
QFrame#automationSourcePanel QComboBox#sourceCompactFilter,
QFrame#automationSourcePanel QLineEdit#sourceCompactSearch,
QFrame#automationSourcePanel QPushButton#automationCompactButton {
    min-height:20px; max-height:22px; font-size:8px;
}
QTableWidget#dashboardSourceTable QHeaderView::section {
    min-height:18px; max-height:20px; font-size:8px; padding:1px 2px;
}
QFrame#automationPreviousPanel QLabel#automationBreakdownFilterLabel {
    font-size:8px; min-height:9px; max-height:11px; padding:0; margin:0;
}
QFrame#automationPreviousPanel QComboBox#breakdownFilter {
    min-height:20px; max-height:21px; font-size:8px; padding-top:0; padding-bottom:0;
}
QLabel#automationBreakdownContext {
    font-size:8px; min-height:12px; max-height:14px; padding:0; margin:0;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    font-size:9px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    min-height:17px; max-height:18px; font-size:8px; padding:0 2px;
}
QFrame#automationPreviousPanel QPushButton#automationCompactButton {
    min-height:20px; max-height:22px; padding:1px 6px; font-size:8px;
}
/* Recovered height belongs to the operational review table. */
QWidget#reviewHeadingPanel { min-height:40px; max-height:44px; }
QTableWidget#attentionTable { min-height:190px; }
"""

# Pass 26R: recon alignment + true 3-bank visibility.
MAIN_STYLE += """
/* Reconciliation closer to KPI strip; KPI internals remain untouched. */
QFrame#automationReconciliationStrip { padding-top:0px; padding-bottom:0px; }
QLabel#automationReconTitle { min-height:15px; max-height:17px; }
QLabel#automationReconLabel { min-height:12px; max-height:14px; }
QLabel#automationReconValue { min-height:15px; max-height:17px; }

/* Exact compact operation-breakdown surface. */
QFrame#automationPreviousPanel QLabel#automationCompactTitle {
    min-height:15px; max-height:17px; font-size:9px;
}
QFrame#automationPreviousPanel QLabel#automationCompactBadge {
    min-height:16px; max-height:18px; font-size:8px; padding:0 5px;
}
QFrame#automationPreviousPanel QLabel#automationBreakdownFilterLabel {
    min-height:8px; max-height:9px; font-size:7px; padding:0; margin:0;
}
QFrame#automationPreviousPanel QComboBox#breakdownFilter {
    min-height:17px; max-height:18px; font-size:8px; padding-top:0; padding-bottom:0;
}
QLabel#automationBreakdownContext {
    min-height:9px; max-height:11px; font-size:7px; padding:0; margin:0;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable {
    font-size:8px;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable QHeaderView::section {
    min-height:15px; max-height:16px; font-size:7px; padding:0 2px;
}
QFrame#automationPreviousPanel QWidget#automationBankCell {
    min-height:18px; max-height:19px; padding:0; margin:0;
}
QFrame#automationPreviousPanel QLabel#automationBankMark {
    min-width:18px; max-width:18px;
    min-height:18px; max-height:18px;
    padding:0; margin:0;
}
QFrame#automationPreviousPanel QLabel#automationBankName {
    font-size:8px; padding:0; margin:0;
}
QFrame#automationPreviousPanel QProgressBar#breakdownShare {
    min-height:9px; max-height:10px; font-size:7px; border-radius:4px;
}
QFrame#automationPreviousPanel QPushButton#automationCompactButton {
    min-height:18px; max-height:19px; padding:0 5px; font-size:7px;
}
"""

# Pass 27: dynamic breakdown viewport + final recon alignment.
MAIN_STYLE += """
QLabel#automationBreakdownNote {
    min-height:0px; max-height:0px; padding:0px; margin:0px; border:none;
}
QFrame#automationPreviousPanel QTableWidget#operationBreakdownTable { margin:0px; }
QFrame#automationPreviousPanel QPushButton#automationCompactButton {
    min-height:18px; max-height:19px; padding:0 5px;
}
"""
