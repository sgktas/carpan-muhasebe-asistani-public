"""Platform sahibinin firma dışı, veri-minimum merkezi yönetim işlemleri."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from psycopg.rows import dict_row

from carpan_platform.config import Settings
from carpan_platform.licensing import normalize_module_entitlements
from carpan_platform.security import verify_password


class PlatformLoginRejected(ValueError):
    """Platform kullanıcısı için kasıtlı olarak genel tutulan giriş hatası."""


SUPPORTED_MODULE_IDS = frozenset({
    "manim_transfer", "report_editing", "bank_reconciliation",
    "cari_reconciliation", "customer_list_import",
})
LICENSE_STATUSES = frozenset({"TRIAL", "ACTIVE", "PAST_DUE", "SUSPENDED", "CANCELLED"})
COMPANY_MUTABLE_STATUSES = frozenset({"ACTIVE", "SUSPENDED"})


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
    enabled_modules: tuple[str, ...] = ()
    license_enforcement_required: bool = False
    license_offline_grace_hours: int = 168

    def as_payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "name": self.name,
            "status": self.status,
            "license": {
                "plan_code": self.license_plan_code,
                "status": self.license_status,
                "enabled_modules": list(self.enabled_modules),
                "enforcement_required": self.license_enforcement_required,
                "offline_grace_hours": self.license_offline_grace_hours,
            },
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


@dataclass(frozen=True)
class ProvisionedCompany:
    company: PlatformCompanySummary
    invitation_token: str
    invitation_expires_at: datetime


@dataclass(frozen=True)
class PlatformAuditEventSummary:
    event_type: str
    outcome: str
    created_at: datetime
    actor_display_name: str | None

    def as_payload(self) -> dict[str, object]:
        return {
            "event_type": self.event_type,
            "outcome": self.outcome,
            "created_at": self.created_at,
            "actor_display_name": self.actor_display_name,
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
    def _append_audit(
        connection: psycopg.Connection,
        *,
        actor_user_id: UUID | None,
        event_type: str,
        outcome: str,
        event_data: dict[str, object] | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO carpan.platform_audit_events(actor_user_id, event_type, outcome, event_data)
            VALUES (%s, %s, %s, %s)
            """,
            (actor_user_id, event_type, outcome, Jsonb(event_data or {})),
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
                       l.plan_code, l.status AS license_status, l.module_entitlements,
                       l.enforce_central, l.offline_grace_hours,
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
                GROUP BY c.id, c.code, c.name, c.status, l.plan_code, l.status,
                         l.module_entitlements, l.enforce_central, l.offline_grace_hours
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
                enabled_modules=normalize_module_entitlements(row["module_entitlements"]),
                license_enforcement_required=bool(row["enforce_central"]) if row["enforce_central"] is not None else False,
                license_offline_grace_hours=int(row["offline_grace_hours"]) if row["offline_grace_hours"] is not None else 168,
            )
            for row in rows
        )
        return PlatformOverview(
            company_count=int(totals["company_count"]),
            active_company_count=int(totals["active_company_count"]),
            active_device_count=int(device_row["active_device_count"]),
            companies=companies,
        )

    def audit_events(self, *, limit: int = 25) -> tuple[PlatformAuditEventSummary, ...]:
        """Sadece işlem türü, sonucu, zamanı ve işlem sahibini döndürür."""
        safe_limit = min(max(int(limit), 1), 50)
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT e.event_type, e.outcome, e.created_at, u.display_name
                FROM carpan.platform_audit_events e
                LEFT JOIN carpan.users u ON u.id = e.actor_user_id
                ORDER BY e.id DESC
                LIMIT %s
                """,
                (safe_limit,),
            ).fetchall()
        return tuple(
            PlatformAuditEventSummary(
                event_type=str(row["event_type"]), outcome=str(row["outcome"]),
                created_at=row["created_at"],
                actor_display_name=str(row["display_name"]) if row["display_name"] else None,
            )
            for row in rows
        )

    @staticmethod
    def _company_input(*, code: str, name: str) -> tuple[str, str]:
        normalized_code = str(code).strip().upper()
        normalized_name = " ".join(str(name).split())
        if not re.fullmatch(r"[A-Z0-9_-]{2,40}", normalized_code):
            raise ValueError("Firma kodu 2-40 karakter; büyük harf, rakam, - veya _ içermeli.")
        if not normalized_name or len(normalized_name) > 160:
            raise ValueError("Firma adı 1-160 karakter olmalı.")
        return normalized_code, normalized_name

    @staticmethod
    def _license_input(*, plan_code: str, status: str, module_ids: list[str], enforce_central: bool, offline_grace_hours: int) -> tuple[str, str, list[str], bool, int]:
        normalized_plan = str(plan_code).strip().upper()
        normalized_status = str(status).strip().upper()
        modules = sorted({str(module_id).strip() for module_id in module_ids if str(module_id).strip()})
        if not re.fullmatch(r"[A-Z0-9_-]{2,40}", normalized_plan):
            raise ValueError("Plan kodu 2-40 karakter; büyük harf, rakam, - veya _ içermeli.")
        if normalized_status not in LICENSE_STATUSES:
            raise ValueError("Lisans durumu geçersiz.")
        if not set(modules).issubset(SUPPORTED_MODULE_IDS):
            raise ValueError("Lisans modüllerinden biri tanınmıyor.")
        grace_hours = int(offline_grace_hours)
        if not 0 <= grace_hours <= 720:
            raise ValueError("Çevrimdışı izin süresi 0-720 saat olmalı.")
        return normalized_plan, normalized_status, modules, bool(enforce_central), grace_hours

    def provision_company(
        self,
        *,
        actor_user_id: UUID,
        code: str,
        name: str,
        admin_username: str,
        admin_display_name: str,
        plan_code: str,
        license_status: str,
        module_ids: list[str],
        enforce_central: bool = False,
        offline_grace_hours: int = 168,
    ) -> ProvisionedCompany:
        """Firma, ilk lisans ve tek kullanımlık ilk yönetici davetini atomik kurar."""
        company_code, company_name = self._company_input(code=code, name=name)
        plan, status, modules, enforce, grace_hours = self._license_input(
            plan_code=plan_code, status=license_status, module_ids=module_ids,
            enforce_central=enforce_central, offline_grace_hours=offline_grace_hours,
        )
        username = str(admin_username).strip().casefold()
        display_name = " ".join(str(admin_display_name).split())
        if not re.fullmatch(r"[a-z0-9._-]{3,80}", username) or not display_name or len(display_name) > 160:
            raise ValueError("İlk yönetici bilgileri geçersiz.")
        invitation_token = secrets.token_urlsafe(32)
        invitation_hash = hashlib.sha256(invitation_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        with self._connection() as connection:
            with connection.transaction():
                if connection.execute("SELECT 1 FROM carpan.companies WHERE code = %s", (company_code,)).fetchone():
                    raise ValueError("Bu firma kodu zaten kullanılıyor.")
                if connection.execute("SELECT 1 FROM carpan.users WHERE username = %s", (username,)).fetchone():
                    raise ValueError("İlk yönetici kullanıcı adı zaten kullanılıyor.")
                company = connection.execute(
                    "INSERT INTO carpan.companies(code, name) VALUES (%s, %s) RETURNING id",
                    (company_code, company_name),
                ).fetchone()
                company_id = company["id"]
                connection.execute(
                    """
                    INSERT INTO carpan.licenses(company_id, plan_code, status, module_entitlements, enforce_central, offline_grace_hours)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (company_id, plan, status, Jsonb(modules), enforce, grace_hours),
                )
                connection.execute(
                    """
                    INSERT INTO carpan.user_invitations(company_id, username, display_name, role, token_hash, expires_at, created_by_user_id)
                    VALUES (%s, %s, %s, 'ADMIN', %s, %s, %s)
                    """,
                    (company_id, username, display_name, invitation_hash, expires_at, actor_user_id),
                )
                self._append_audit(
                    connection,
                    actor_user_id=actor_user_id,
                    event_type="COMPANY_PROVISIONED",
                    outcome="SUCCESS",
                    event_data={"company_code": company_code},
                )
        return ProvisionedCompany(
            company=PlatformCompanySummary(company_code, company_name, "ACTIVE", plan, status, 0),
            invitation_token=invitation_token,
            invitation_expires_at=expires_at,
        )

    def update_license(
        self,
        *,
        actor_user_id: UUID,
        company_code: str,
        plan_code: str,
        license_status: str,
        module_ids: list[str],
        enforce_central: bool,
        offline_grace_hours: int,
    ) -> None:
        """Firma lisansını yeni satır eklemeden, denetlenebilir tek kayıtta günceller."""
        code, _ = self._company_input(code=company_code, name="Geçici")
        plan, status, modules, enforce, grace_hours = self._license_input(
            plan_code=plan_code, status=license_status, module_ids=module_ids,
            enforce_central=enforce_central, offline_grace_hours=offline_grace_hours,
        )
        with self._connection() as connection:
            with connection.transaction():
                company = connection.execute("SELECT id FROM carpan.companies WHERE code = %s FOR UPDATE", (code,)).fetchone()
                if company is None:
                    raise LookupError("Firma bulunamadı.")
                updated = connection.execute(
                    """
                    UPDATE carpan.licenses
                    SET plan_code=%s, status=%s, module_entitlements=%s,
                        enforce_central=%s, offline_grace_hours=%s
                    WHERE id = (
                        SELECT id FROM carpan.licenses WHERE company_id=%s
                        ORDER BY created_at DESC LIMIT 1 FOR UPDATE
                    )
                    """,
                    (plan, status, Jsonb(modules), enforce, grace_hours, company["id"]),
                ).rowcount
                if not updated:
                    connection.execute(
                        """
                        INSERT INTO carpan.licenses(company_id, plan_code, status, module_entitlements, enforce_central, offline_grace_hours)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (company["id"], plan, status, Jsonb(modules), enforce, grace_hours),
                    )
                self._append_audit(
                    connection,
                    actor_user_id=actor_user_id,
                    event_type="LICENSE_UPDATED",
                    outcome="SUCCESS",
                    event_data={"company_code": code, "license_status": status},
                )

    def update_company_status(
        self,
        *,
        actor_user_id: UUID,
        company_code: str,
        company_status: str,
    ) -> None:
        """Firma çalışma alanını geri alınabilir biçimde etkinleştirir ya da askıya alır.

        Cihazlar ve lisans kaydı korunur. Merkezi istek doğrulaması şirketin
        ``ACTIVE`` durumunu her korumalı istekte yeniden kontrol ettiği için
        askıya alma, açık masaüstü oturumlarında da bir sonraki merkezi istekte
        uygulanır; yeniden etkinleştirme ise yeni kurulum gerektirmez.
        """
        code, _ = self._company_input(code=company_code, name="Geçici")
        normalized_status = str(company_status).strip().upper()
        if normalized_status not in COMPANY_MUTABLE_STATUSES:
            raise ValueError("Firma durumu yalnız Etkin veya Askıda olabilir.")
        with self._connection() as connection:
            with connection.transaction():
                updated = connection.execute(
                    "UPDATE carpan.companies SET status=%s WHERE code=%s",
                    (normalized_status, code),
                ).rowcount
                if not updated:
                    raise LookupError("Firma bulunamadı.")
                self._append_audit(
                    connection,
                    actor_user_id=actor_user_id,
                    event_type="COMPANY_STATUS_UPDATED",
                    outcome="SUCCESS",
                    event_data={"company_code": code, "company_status": normalized_status},
                )
