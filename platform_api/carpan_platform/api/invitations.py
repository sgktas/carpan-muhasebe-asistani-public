from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import psycopg

from carpan_platform.api.dependencies import get_settings
from carpan_platform.config import Settings
from carpan_platform.management import ManagementRepository
from carpan_platform.security import hash_password


router = APIRouter(prefix="/v1/invitations", tags=["invitations"])


class InvitationAcceptanceRequest(BaseModel):
    token: str = Field(min_length=40, max_length=512)
    password: str = Field(min_length=12, max_length=512)


@router.post("/accept")
def accept(payload: InvitationAcceptanceRequest, settings: Settings = Depends(get_settings)) -> dict[str, str]:
    try:
        password_hash = hash_password(payload.password)
        accepted = ManagementRepository(settings).accept_invitation(token=payload.token, password_hash=password_hash)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from None
    except psycopg.Error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Davet servisine şu an ulaşılamıyor.") from None
    if accepted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Davet geçersiz, kullanılmış veya süresi dolmuş.")
    return accepted
