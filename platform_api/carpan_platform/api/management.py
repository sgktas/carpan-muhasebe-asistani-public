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
