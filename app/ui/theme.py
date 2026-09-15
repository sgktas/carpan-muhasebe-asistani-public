from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
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
