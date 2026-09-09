"""Platform sahibinin firma dışı, veri-minimum merkezi yönetim işlemleri."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from carpan_platform.config import Settings
from carpan_platform.security import verify_password


class PlatformLoginRejected(ValueError):
    """Platform kullanıcısı için kasıtlı olarak genel tutulan giriş hatası."""


@dataclass(frozen=True)
class PlatformOperator:
    user_id: UUID
    display_name: str


@dataclass(frozen=True)
class PlatformCompanySummary:
    code: str
    name: str
    status: str
    license_plan_code: str | None
    license_status: str | None
    active_device_count: int

    def as_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name": self.name,
            "status": self.status,
            "license": {"plan_code": self.license_plan_code, "status": self.license_status},
            "devices": {"active_count": self.active_device_count},
        }


@dataclass(frozen=True)
class PlatformOverview:
    company_count: int
    active_company_count: int
    active_device_count: int
    companies: tuple[PlatformCompanySummary, ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "companies": {
                "total_count": self.company_count,
                "active_count": self.active_company_count,
                "items": [company.as_payload() for company in self.companies],
            },
            "devices": {"active_count": self.active_device_count},
        }


class PlatformOwnerRepository:
    """Yalnız sunucudaki sahip bağlantısı ile çalışan, finansal veri taşımayan katman."""

    def __init__(self, settings: Settings):
        if not settings.owner_database_url:
            raise RuntimeError("Platform sahibi veritabanı bağlantısı yapılandırılmamış.")
        self.settings = settings

    def _connection(self) -> psycopg.Connection:
        return psycopg.connect(str(self.settings.owner_database_url), row_factory=dict_row)

    @staticmethod
    def _append_audit(connection: psycopg.Connection, *, actor_user_id: UUID | None, event_type: str, outcome: str) -> None:
        connection.execute(
            "INSERT INTO carpan.platform_audit_events(actor_user_id, event_type, outcome) VALUES (%s, %s, %s)",
            (actor_user_id, event_type, outcome),
        )

    def authenticate(self, *, username: str, password: str) -> PlatformOperator:
        normalized_username = str(username).strip().casefold()
        with self._connection() as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT u.id, u.display_name, u.password_hash
                    FROM carpan.platform_operators p
                    JOIN carpan.users u ON u.id = p.user_id
                    WHERE u.username = %s AND p.active AND u.status = 'ACTIVE'
                    FOR UPDATE OF u
                    """,
                    (normalized_username,),
                ).fetchone()
                if row is None or not verify_password(password, str(row["password_hash"])):
                    self._append_audit(connection, actor_user_id=None, event_type="PLATFORM_LOGIN", outcome="FAILED")
                    raise PlatformLoginRejected("Giriş reddedildi.")
                operator = PlatformOperator(user_id=UUID(str(row["id"])), display_name=str(row["display_name"]))
                self._append_audit(connection, actor_user_id=operator.user_id, event_type="PLATFORM_LOGIN", outcome="SUCCESS")
        return operator

    def operator_is_active(self, user_id: UUID) -> bool:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM carpan.platform_operators p
                JOIN carpan.users u ON u.id = p.user_id
                WHERE p.user_id = %s AND p.active AND u.status = 'ACTIVE'
                """,
                (user_id,),
            ).fetchone()
        return row is not None

    def overview(self) -> PlatformOverview:
        """Sadece firma/lisans/cihaz sağlığı; müşteri ve finansal veri yoktur."""
        with self._connection() as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS company_count,
                       COUNT(*) FILTER (WHERE status = 'ACTIVE') AS active_company_count
                FROM carpan.companies
                """
            ).fetchone()
            device_row = connection.execute(
                "SELECT COUNT(*) AS active_device_count FROM carpan.device_registrations WHERE status = 'ACTIVE'"
            ).fetchone()
            rows = connection.execute(
                """
                SELECT c.code, c.name, c.status,
                       l.plan_code, l.status AS license_status,
                       COUNT(d.id) FILTER (WHERE d.status = 'ACTIVE') AS active_device_count
                FROM carpan.companies c
                LEFT JOIN LATERAL (
                    SELECT plan_code, status
                    FROM carpan.licenses
                    WHERE company_id = c.id
                    ORDER BY CASE status WHEN 'ACTIVE' THEN 0 WHEN 'TRIAL' THEN 1 ELSE 2 END, created_at DESC
                    LIMIT 1
                ) l ON true
                LEFT JOIN carpan.device_registrations d ON d.company_id = c.id
                GROUP BY c.id, c.code, c.name, c.status, l.plan_code, l.status
                ORDER BY lower(c.name), lower(c.code)
                LIMIT 200
                """
            ).fetchall()
        companies = tuple(
            PlatformCompanySummary(
                code=str(row["code"]), name=str(row["name"]), status=str(row["status"]),
                license_plan_code=str(row["plan_code"]) if row["plan_code"] else None,
                license_status=str(row["license_status"]) if row["license_status"] else None,
                active_device_count=int(row["active_device_count"]),
            )
            for row in rows
        )
        return PlatformOverview(
            company_count=int(totals["company_count"]),
            active_company_count=int(totals["active_company_count"]),
            active_device_count=int(device_row["active_device_count"]),
            companies=companies,
        )
