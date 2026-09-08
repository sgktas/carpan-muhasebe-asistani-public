from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EntitlementSet:
    enabled_modules: frozenset[str]

    def allows(self, module_id: str) -> bool:
        return module_id in self.enabled_modules

    def intersect(self, allowed_module_ids: Iterable[str]) -> "EntitlementSet":
        """Yerel rol yetkisini merkezi lisansla birlikte değerlendirir."""
        allowed = frozenset(str(module_id) for module_id in allowed_module_ids)
        return EntitlementSet(self.enabled_modules & allowed)


def local_development_entitlements(module_ids: Iterable[str]) -> EntitlementSet:
    """Satış/lisans sunucusu gelene kadar bütün kayıtlı modülleri açar.

    Arayüz doğrudan bu sözleşmeyi kullandığı için ileride imzalı lisans veya
    çevrimiçi entitlement servisi eklemek menü mimarisini değiştirmez.
    """
    return EntitlementSet(frozenset(str(module_id) for module_id in module_ids))


def effective_entitlements(
    *,
    local_module_ids: Iterable[str],
    central_module_ids: Iterable[str] | None,
    central_license_usable: bool | None,
) -> EntitlementSet:
    """Merkezi lisans devreye girene kadar yerel rol erişimini kesintisiz korur.

    ``None`` merkezi servisin henüz yapılandırılmadığını veya çevrimdışı
    olduğunu ifade eder. ``False`` ise merkezi lisansın açıkça geçersiz
    olduğunu belirtir ve modülleri kapatır.
    """
    local = frozenset(str(module_id) for module_id in local_module_ids)
    if central_license_usable is None:
        return EntitlementSet(local)
    if not central_license_usable:
        return EntitlementSet(frozenset())
    return EntitlementSet(local & frozenset(str(module_id) for module_id in central_module_ids or ()))
