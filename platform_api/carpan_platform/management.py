"""Web yönetim paneli için firma kapsamlı, özet merkezi veriler."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from carpan_platform.config import Settings
from carpan_platform.database import tenant_transaction
from carpan_platform.licensing import normalize_module_entitlements


@dataclass(frozen=True)
class ManagementOverview:
    company_code: str
    company_name: str
    company_status: str
    active_user_count: int
    role_counts: dict[str, int]
    active_device_count: int
    revoked_device_count: int
    license_plan_code: str | None
    license_status: str | None
    license_expires_at: datetime | None
    enabled_modules: tuple[str, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "company": {
                "code": self.company_code,
                "name": self.company_name,
                "status": self.company_status,
            },
            "users": {
                "active_count": self.active_user_count,
                "roles": self.role_counts,
            },
            "devices": {
                "active_count": self.active_device_count,
                "revoked_count": self.revoked_device_count,
            },
            "license": {
                "plan_code": self.license_plan_code,
                "status": self.license_status,
                "expires_at": self.license_expires_at,
                "enabled_modules": list(self.enabled_modules),
            },
        }


class ManagementRepository:
    """RLS bağlamından çıkmadan yönetim ekranı özetini okur."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def overview(self, company_id: UUID) -> ManagementOverview:
        with tenant_transaction(self.settings, company_id) as connection:
            company = connection.execute(
                "SELECT code, name, status FROM carpan.companies WHERE id = %s",
                (company_id,),
            ).fetchone()
            if company is None:
                raise LookupError("Firma bulunamadı.")
            role_rows = connection.execute(
                """
                SELECT m.role, COUNT(*) AS count
                FROM carpan.company_memberships m
                JOIN carpan.users u ON u.id = m.user_id
                WHERE m.company_id = %s AND m.active AND u.status = 'ACTIVE'
                GROUP BY m.role
                """,
                (company_id,),
            ).fetchall()
            device_rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM carpan.device_registrations
                WHERE company_id = %s
                GROUP BY status
                """,
                (company_id,),
            ).fetchall()
            license_row = connection.execute(
                """
                SELECT plan_code, status, expires_at, module_entitlements
                FROM carpan.licenses
                WHERE company_id = %s
                ORDER BY
                    CASE status WHEN 'ACTIVE' THEN 0 WHEN 'TRIAL' THEN 1 ELSE 2 END,
                    created_at DESC
                LIMIT 1
                """,
                (company_id,),
            ).fetchone()

        role_counts = {str(row["role"]): int(row["count"]) for row in role_rows}
        device_counts = {str(row["status"]): int(row["count"]) for row in device_rows}
        return ManagementOverview(
            company_code=str(company["code"]),
            company_name=str(company["name"]),
            company_status=str(company["status"]),
            active_user_count=sum(role_counts.values()),
            role_counts=role_counts,
            active_device_count=device_counts.get("ACTIVE", 0),
            revoked_device_count=device_counts.get("REVOKED", 0),
            license_plan_code=str(license_row["plan_code"]) if license_row else None,
            license_status=str(license_row["status"]) if license_row else None,
            license_expires_at=license_row["expires_at"] if license_row else None,
            enabled_modules=normalize_module_entitlements(
                license_row["module_entitlements"] if license_row else []
            ),
        )
