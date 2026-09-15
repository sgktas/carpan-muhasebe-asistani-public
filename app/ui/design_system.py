"""Central visual vocabulary for the Çarpan desktop workspace.

The first UI phase keeps tokens separate from accounting and persistence code so
future theme variants can replace this palette without page-level rewrites.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    font_family: str = "Segoe UI"
    page_title_size: int = 26
    section_title_size: int = 18
    panel_title_size: int = 15
    body_size: int = 13
    metadata_size: int = 11
    financial_value_size: int = 28
    app_background: str = "#F4F6F8"
    surface: str = "#FFFFFF"
    surface_secondary: str = "#F8F9FB"
    sidebar: str = "#142033"
    sidebar_hover: str = "#1C2B42"
    sidebar_selected: str = "#243A60"
    text_primary: str = "#172033"
    text_secondary: str = "#667085"
    text_muted: str = "#98A2B3"
    border: str = "#E3E7ED"
    border_strong: str = "#D2D8E2"
    brand: str = "#315BE8"
    brand_hover: str = "#274CCA"
    brand_soft: str = "#EEF2FF"
    success: str = "#18A66A"
    success_soft: str = "#EAF8F1"
    warning: str = "#E9A11B"
    warning_soft: str = "#FFF6E3"
    critical: str = "#E24B4B"
    critical_soft: str = "#FDECEC"
    info: str = "#3978E6"
    info_soft: str = "#EDF4FF"
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 20
    space_6: int = 24
    space_7: int = 32
    space_8: int = 40
    space_9: int = 48
    radius_small: int = 6
    radius_control: int = 8
    radius_panel: int = 10
    radius_dialog: int = 12


TOKENS = DesignTokens()


STATUS_TOKENS = {
    "ACTIVE": (TOKENS.success, TOKENS.success_soft, "Aktif"),
    "LOCKED": (TOKENS.text_muted, TOKENS.surface_secondary, "Ek modül"),
    "UNCONFIGURED": (TOKENS.warning, TOKENS.warning_soft, "Kurulum gerekli"),
    "COMING_SOON": (TOKENS.info, TOKENS.info_soft, "Yakında"),
}
