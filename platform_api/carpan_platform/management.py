"""Web yönetim paneli için firma kapsamlı, özet merkezi veriler."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets
from uuid import UUID

import psycopg

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


@dataclass(frozen=True)
class TeamMemberSummary:
    username: str
    display_name: str
    role: str
    active: bool
    user_status: str
    last_login_at: datetime | None

    def as_payload(self) -> dict[str, object]:
        return {
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "active": self.active,
            "status": self.user_status,
            "last_login_at": self.last_login_at,
        }


@dataclass(frozen=True)
class DeviceSummary:
    device_label: str | None
    status: str
    assigned_username: str
    last_seen_at: datetime
    created_at: datetime

    def as_payload(self) -> dict[str, object]:
        return {
            "label": self.device_label,
            "status": self.status,
            "assigned_username": self.assigned_username,
            "last_seen_at": self.last_seen_at,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class Invitation:
    token: str
    expires_at: datetime


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

    def team_members(self, company_id: UUID) -> tuple[TeamMemberSummary, ...]:
        with tenant_transaction(self.settings, company_id) as connection:
            rows = connection.execute(
                """
                SELECT u.username, u.display_name, u.status, u.last_login_at,
                       m.role, m.active
                FROM carpan.company_memberships m
                JOIN carpan.users u ON u.id = m.user_id
                WHERE m.company_id = %s
                ORDER BY lower(u.display_name), lower(u.username)
                """,
                (company_id,),
            ).fetchall()
        return tuple(
            TeamMemberSummary(
                username=str(row["username"]),
                display_name=str(row["display_name"]),
                role=str(row["role"]),
                active=bool(row["active"]),
                user_status=str(row["status"]),
                last_login_at=row["last_login_at"],
            )
            for row in rows
        )

    def devices(self, company_id: UUID) -> tuple[DeviceSummary, ...]:
        with tenant_transaction(self.settings, company_id) as connection:
            rows = connection.execute(
                """
                SELECT d.device_label, d.status, d.last_seen_at, d.created_at,
                       u.username
                FROM carpan.device_registrations d
                JOIN carpan.users u ON u.id = d.user_id
                WHERE d.company_id = %s
                ORDER BY d.status, d.last_seen_at DESC
                """,
                (company_id,),
            ).fetchall()
        return tuple(
            DeviceSummary(
                device_label=str(row["device_label"]) if row["device_label"] else None,
                status=str(row["status"]),
                assigned_username=str(row["username"]),
                last_seen_at=row["last_seen_at"],
                created_at=row["created_at"],
            )
            for row in rows
        )

    def create_invitation(self, *, company_id: UUID, actor_user_id: UUID, username: str, display_name: str, role: str) -> Invitation:
        normalized_username = str(username).strip().casefold()
        if not re.fullmatch(r"[a-z0-9._-]{3,80}", normalized_username):
            raise ValueError("Kullanıcı adı 3-80 karakter; küçük harf, rakam, ., _ veya - içermeli.")
        safe_name = " ".join(str(display_name).split())
        normalized_role = str(role).strip().upper()
        if not safe_name or len(safe_name) > 160 or normalized_role not in {"ADMIN", "OPERATOR", "APPROVER", "AUDITOR"}:
            raise ValueError("Davet bilgileri geçersiz.")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        with tenant_transaction(self.settings, company_id) as connection:
            member = connection.execute(
                "SELECT 1 FROM carpan.company_memberships m JOIN carpan.users u ON u.id=m.user_id WHERE m.company_id=%s AND u.username=%s",
                (company_id, normalized_username),
            ).fetchone()
            if member:
                raise ValueError("Bu kullanıcı zaten firma ekibinde.")
            connection.execute("UPDATE carpan.user_invitations SET revoked_at=now() WHERE company_id=%s AND username=%s AND accepted_at IS NULL AND revoked_at IS NULL", (company_id, normalized_username))
            connection.execute(
                "INSERT INTO carpan.user_invitations(company_id, username, display_name, role, token_hash, expires_at, created_by_user_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (company_id, normalized_username, safe_name, normalized_role, token_hash, expires_at, actor_user_id),
            )
        return Invitation(token=token, expires_at=expires_at)

    def accept_invitation(self, *, token: str, password_hash: str) -> dict[str, str] | None:
        token_hash = hashlib.sha256(str(token).strip().encode("utf-8")).hexdigest()
        with psycopg.connect(str(self.settings.database_url)) as connection:
            row = connection.execute("SELECT * FROM carpan.accept_user_invitation(%s, %s)", (token_hash, password_hash)).fetchone()
        if row is None:
            return None
        return {"company_code": str(row[0]), "username": str(row[1]), "display_name": str(row[2]), "role": str(row[3])}
