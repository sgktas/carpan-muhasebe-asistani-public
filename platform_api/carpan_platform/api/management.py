from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
import psycopg

from carpan_platform.api.dependencies import get_settings, require_roles
from carpan_platform.config import Settings
from carpan_platform.database import DatabaseConfigurationError
from carpan_platform.management import ManagementRepository
from carpan_platform.security import AccessTokenClaims


router = APIRouter(prefix="/v1/management", tags=["management"])


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
