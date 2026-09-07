from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
import psycopg

from carpan_platform.api.auth import get_settings
from carpan_platform.config import Settings
from carpan_platform.database import DatabaseConfigurationError
from carpan_platform.licensing import LicensingRepository
from carpan_platform.security import TokenError, read_access_token


router = APIRouter(prefix="/v1", tags=["licensing"])
bearer_scheme = HTTPBearer(auto_error=False)


class InstallationActivationRequest(BaseModel):
    installation_id: str = Field(min_length=16, max_length=200)
    device_label: str | None = Field(default=None, max_length=160)


def _claims(
    credentials: HTTPAuthorizationCredentials | None,
    settings: Settings,
):
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Giriş gerekli.")
    try:
        return read_access_token(settings, credentials.credentials)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum geçersiz.") from None


@router.get("/license")
def current_license(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    claims = _claims(credentials, settings)
    try:
        license_info = LicensingRepository(settings).current_license(claims.company_id)
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lisans servisine şu an ulaşılamıyor.",
        ) from None
    if license_info is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu firma için aktif lisans bulunamadı.")
    return {
        "plan_code": license_info.plan_code,
        "status": license_info.status,
        "expires_at": license_info.expires_at,
        "enabled_modules": license_info.enabled_modules,
        "usable": license_info.is_usable(),
    }


@router.post("/devices/activate", status_code=status.HTTP_204_NO_CONTENT)
def activate_installation(
    payload: InstallationActivationRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    claims = _claims(credentials, settings)
    try:
        LicensingRepository(settings).activate_installation(
            company_id=claims.company_id,
            user_id=claims.user_id,
            installation_id=payload.installation_id,
            device_label=payload.device_label,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cihaz aktivasyon servisine şu an ulaşılamıyor.",
        ) from None
