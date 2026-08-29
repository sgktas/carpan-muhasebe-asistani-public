from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class ModuleManifest:
    module_id: str
    name: str
    nav_label: str
    version: str
    icon_name: str
    badge: str
    description: str
    page_factory: Callable[[], QWidget]
