from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
import psycopg

from carpan_platform.config import Settings
from carpan_platform.database import DatabaseConfigurationError
from carpan_platform.identity_repository import CentralIdentityRepository, LoginRejected
from carpan_platform.security import TokenError, create_access_token, read_access_token


router = APIRouter(prefix="/v1/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    company_code: str = Field(min_length=2, max_length=40)
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=512)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int = 900
    refresh_expires_in_seconds: int = 2_592_000
    display_name: str
    role: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=40, max_length=512)


def get_settings() -> Settings:
    return Settings.from_environment()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, settings: Settings = Depends(get_settings)) -> LoginResponse:
    if not settings.database_configured or not settings.token_signing_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Merkezi giriş servisi henüz yapılandırılmadı.",
        )
    try:
        identity = CentralIdentityRepository(settings).authenticate(
            company_code=payload.company_code,
            username=payload.username,
            password=payload.password,
        )
        token = create_access_token(
            settings,
            user_id=identity["user_id"],
            company_id=identity["company_id"],
            role=identity["role"],
        )
        refresh_token = CentralIdentityRepository(settings).create_refresh_session(
            company_id=identity["company_id"], user_id=identity["user_id"]
        )
    except LoginRejected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firma, kullanıcı adı veya parola hatalı.",
        ) from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Merkezi giriş servisine şu an ulaşılamıyor.",
        ) from None
    return LoginResponse(
        access_token=token,
        refresh_token=refresh_token,
        display_name=identity["display_name"],
        role=identity["role"],
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(payload: RefreshRequest, settings: Settings = Depends(get_settings)) -> LoginResponse:
    if not settings.database_configured or not settings.token_signing_configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Merkezi giriş servisi henüz yapılandırılmadı.")
    try:
        repository = CentralIdentityRepository(settings)
        identity = repository.rotate_refresh_session(payload.refresh_token)
        access_token = create_access_token(settings, user_id=identity["user_id"], company_id=identity["company_id"], role=identity["role"])
        refresh_token = repository.create_refresh_session(company_id=identity["company_id"], user_id=identity["user_id"])
    except (LoginRejected, TokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum geçersiz.") from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Merkezi giriş servisine şu an ulaşılamıyor.") from None
    return LoginResponse(access_token=access_token, refresh_token=refresh_token, display_name=identity["display_name"], role=identity["role"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), settings: Settings = Depends(get_settings)) -> None:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Giriş gerekli.")
    try:
        claims = read_access_token(settings, credentials.credentials)
        CentralIdentityRepository(settings).revoke_refresh_session(company_id=claims.company_id, user_id=claims.user_id, raw_token=payload.refresh_token)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum geçersiz.") from None
    except (DatabaseConfigurationError, psycopg.Error):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Merkezi giriş servisine şu an ulaşılamıyor.") from None


@router.get("/me")
def me(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Giriş gerekli.")
    try:
        claims = read_access_token(settings, credentials.credentials)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum geçersiz.") from None
    return {
        "user_id": str(claims.user_id),
        "company_id": str(claims.company_id),
        "role": claims.role,
    }
