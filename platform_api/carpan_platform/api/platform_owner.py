"""Çarpan platform sahibi için firma dışı, veri-minimum yönetim uçları."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
import psycopg

from carpan_platform.api.dependencies import current_platform_operator, get_settings
from carpan_platform.config import Settings
from carpan_platform.platform_owner import PlatformLoginRejected, PlatformOwnerRepository
from carpan_platform.security import PlatformOperatorClaims, create_platform_operator_token


router = APIRouter(prefix="/v1/platform", tags=["platform-owner"])


class PlatformLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=512)


class CompanyProvisionRequest(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=1, max_length=160)
    admin_username: str = Field(min_length=3, max_length=80)
    admin_display_name: str = Field(min_length=1, max_length=160)
    plan_code: str = Field(min_length=2, max_length=40)
    license_status: str = Field(default="TRIAL", min_length=5, max_length=20)
    module_ids: list[str] = Field(default_factory=list, max_length=20)
    enforce_central: bool = False
    offline_grace_hours: int = Field(default=168, ge=0, le=720)


class LicenseUpdateRequest(BaseModel):
    plan_code: str = Field(min_length=2, max_length=40)
    license_status: str = Field(min_length=5, max_length=20)
    module_ids: list[str] = Field(default_factory=list, max_length=20)
    enforce_central: bool = False
    offline_grace_hours: int = Field(default=168, ge=0, le=720)


@router.post("/auth/login")
def login(payload: PlatformLoginRequest, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    if not settings.platform_owner_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform sahibi yönetimi henüz yapılandırılmadı.",
        )
    try:
        operator = PlatformOwnerRepository(settings).authenticate(
            username=payload.username, password=payload.password,
        )
        return {
            "access_token": create_platform_operator_token(settings, user_id=operator.user_id),
            "token_type": "bearer",
            "expires_in_seconds": 900,
            "display_name": operator.display_name,
        }
    except PlatformLoginRejected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı adı veya parola hatalı.") from None
    except (RuntimeError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Platform girişi şu an kullanılamıyor.") from None


@router.get("/overview")
def overview(
    _: PlatformOperatorClaims = Depends(current_platform_operator),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        return PlatformOwnerRepository(settings).overview().as_payload()
    except (RuntimeError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform yönetim özeti şu an okunamıyor.",
        ) from None


@router.get("/audit-events")
def audit_events(
    limit: int = Query(default=25, ge=1, le=50),
    _: PlatformOperatorClaims = Depends(current_platform_operator),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        events = PlatformOwnerRepository(settings).audit_events(limit=limit)
        return {"events": [event.as_payload() for event in events]}
    except (RuntimeError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform güvenlik kayıtları şu an okunamıyor.",
        ) from None


@router.post("/companies", status_code=status.HTTP_201_CREATED)
def provision_company(
    payload: CompanyProvisionRequest,
    claims: PlatformOperatorClaims = Depends(current_platform_operator),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    try:
        provisioned = PlatformOwnerRepository(settings).provision_company(
            actor_user_id=claims.user_id,
            code=payload.code,
            name=payload.name,
            admin_username=payload.admin_username,
            admin_display_name=payload.admin_display_name,
            plan_code=payload.plan_code,
            license_status=payload.license_status,
            module_ids=payload.module_ids,
            enforce_central=payload.enforce_central,
            offline_grace_hours=payload.offline_grace_hours,
        )
        return {
            "company": provisioned.company.as_payload(),
            "initial_admin_invitation": {
                "token": provisioned.invitation_token,
                "expires_at": provisioned.invitation_expires_at,
            },
        }
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except (RuntimeError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Firma kurulamadı.") from None


@router.put("/companies/{company_code}/license", status_code=status.HTTP_204_NO_CONTENT)
def update_license(
    company_code: str,
    payload: LicenseUpdateRequest,
    claims: PlatformOperatorClaims = Depends(current_platform_operator),
    settings: Settings = Depends(get_settings),
) -> None:
    try:
        PlatformOwnerRepository(settings).update_license(
            actor_user_id=claims.user_id,
            company_code=company_code,
            plan_code=payload.plan_code,
            license_status=payload.license_status,
            module_ids=payload.module_ids,
            enforce_central=payload.enforce_central,
            offline_grace_hours=payload.offline_grace_hours,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firma bulunamadı.") from None
    except (RuntimeError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Lisans güncellenemedi.") from None
