from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
import psycopg

from carpan_platform.api.dependencies import get_settings, require_roles
from carpan_platform.config import Settings
from carpan_platform.database import DatabaseConfigurationError
from carpan_platform.management import ManagementRepository
from carpan_platform.security import AccessTokenClaims


router = APIRouter(prefix="/v1/management", tags=["management"])


class InvitationRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    display_name: str = Field(min_length=1, max_length=160)
    role: str = Field(min_length=4, max_length=30)


class MemberUpdateRequest(BaseModel):
    role: str | None = Field(default=None, min_length=4, max_length=30)
    active: bool | None = None


class DeviceRevocationRequest(BaseModel):
    assigned_username: str = Field(min_length=3, max_length=80)
    device_label: str | None = Field(default=None, max_length=160)


@router.get("/overview")
def overview(
    claims: AccessTokenClaims = Depends(require_roles("ADMIN")),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return ManagementRepository(settings).overview(claims.company_id).as_payload()
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma bulunamadı.") from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Merkezi yönetim verisine şu an ulaşılamıyor.",
        ) from None


@router.get("/team")
def team(
    claims: AccessTokenClaims = Depends(require_roles("ADMIN")),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        members = ManagementRepository(settings).team_members(claims.company_id)
        return {"members": [member.as_payload() for member in members]}
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Merkezi ekip verisine şu an ulaşılamıyor.",
        ) from None


@router.get("/devices")
def devices(
    claims: AccessTokenClaims = Depends(require_roles("ADMIN")),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        records = ManagementRepository(settings).devices(claims.company_id)
        return {"devices": [record.as_payload() for record in records]}
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Merkezi cihaz verisine şu an ulaşılamıyor.",
        ) from None


@router.get("/audit-events")
def audit_events(
    limit: int = Query(default=25, ge=1, le=50),
    claims: AccessTokenClaims = Depends(require_roles("ADMIN")),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        events = ManagementRepository(settings).audit_events(claims.company_id, limit=limit)
        return {"events": [event.as_payload() for event in events]}
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Güvenlik kayıtları şu an okunamıyor.",
        ) from None


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(
    payload: InvitationRequest,
    claims: AccessTokenClaims = Depends(require_roles("ADMIN")),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        invitation = ManagementRepository(settings).create_invitation(
            company_id=claims.company_id, actor_user_id=claims.user_id,
            username=payload.username, display_name=payload.display_name, role=payload.role,
        )
        return {"invite_token": invitation.token, "expires_at": invitation.expires_at}
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Merkezi davet servisine şu an ulaşılamıyor.") from None


@router.patch("/team/{username}", status_code=status.HTTP_204_NO_CONTENT)
def update_team_member(username: str, payload: MemberUpdateRequest, claims: AccessTokenClaims = Depends(require_roles("ADMIN")), settings: Settings = Depends(get_settings)) -> None:
    try:
        ManagementRepository(settings).update_member(company_id=claims.company_id, actor_user_id=claims.user_id, username=username, role=payload.role.upper() if payload.role else None, active=payload.active)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ekip kullanıcısı bulunamadı.") from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Ekip kaydı güncellenemedi.") from None


@router.post("/devices/revoke", status_code=status.HTTP_204_NO_CONTENT)
def revoke_device(
    payload: DeviceRevocationRequest,
    claims: AccessTokenClaims = Depends(require_roles("ADMIN")),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        ManagementRepository(settings).revoke_device(
            company_id=claims.company_id,
            actor_user_id=claims.user_id,
            assigned_username=payload.assigned_username,
            device_label=payload.device_label,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Etkin cihaz bulunamadı.") from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cihaz kaydı iptal edilemedi.") from None
