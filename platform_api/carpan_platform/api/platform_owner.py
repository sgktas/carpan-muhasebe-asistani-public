"""Çarpan platform sahibi için firma dışı, veri-minimum yönetim uçları."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
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
