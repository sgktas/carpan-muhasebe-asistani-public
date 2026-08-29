from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EntitlementSet:
    enabled_modules: frozenset[str]

    def allows(self, module_id: str) -> bool:
        return module_id in self.enabled_modules


def local_development_entitlements(module_ids: Iterable[str]) -> EntitlementSet:
    """Satış/lisans sunucusu gelene kadar bütün kayıtlı modülleri açar.

    Arayüz doğrudan bu sözleşmeyi kullandığı için ileride imzalı lisans veya
    çevrimiçi entitlement servisi eklemek menü mimarisini değiştirmez.
    """
    return EntitlementSet(frozenset(str(module_id) for module_id in module_ids))
