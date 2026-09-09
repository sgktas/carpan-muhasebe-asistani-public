from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from carpan_platform.config import Settings


ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 30
PASSWORD_HASHER = PasswordHash.recommended()


class TokenError(ValueError):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: UUID
    company_id: UUID
    role: str
    expires_at: datetime


@dataclass(frozen=True)
class PlatformOperatorClaims:
    user_id: UUID
    expires_at: datetime


def create_refresh_token() -> str:
    """İstemciye yalnız bir kez verilecek, yüksek entropili oturum yenileme değeri."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    value = str(token or "").strip()
    if len(value) < 40:
        raise TokenError("Geçersiz oturum yenileme belirteci.")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def refresh_token_expiry(now: datetime | None = None) -> datetime:
    return (now or datetime.now(timezone.utc)) + timedelta(days=REFRESH_TOKEN_DAYS)


def hash_password(password: str) -> str:
    _validate_password(password)
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_HASHER.verify(password, password_hash)


def create_access_token(
    settings: Settings,
    *,
    user_id: UUID,
    company_id: UUID,
    role: str,
    now: datetime | None = None,
) -> str:
    secret = _token_secret(settings)
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode(
        {
            "sub": str(user_id),
            "company_id": str(company_id),
            "role": role,
            "iss": settings.jwt_issuer,
            "iat": issued_at,
            "exp": expires_at,
        },
        secret,
        algorithm="HS256",
    )


def read_access_token(settings: Settings, token: str) -> AccessTokenClaims:
    try:
        payload = jwt.decode(
            token,
            _token_secret(settings),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "company_id", "role", "exp", "iss"]},
        )
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        return AccessTokenClaims(
            user_id=UUID(str(payload["sub"])),
            company_id=UUID(str(payload["company_id"])),
            role=str(payload["role"]),
            expires_at=expires_at,
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise TokenError("Geçersiz veya süresi dolmuş erişim belirteci.") from error


def create_platform_operator_token(
    settings: Settings, *, user_id: UUID, now: datetime | None = None,
) -> str:
    """Firma tokenından ayrık, yalnız merkezi platform paneli tokenı üretir."""
    secret = _token_secret(settings)
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode(
        {
            "sub": str(user_id),
            "scope": "platform-owner",
            "iss": settings.jwt_issuer,
            "iat": issued_at,
            "exp": expires_at,
        },
        secret,
        algorithm="HS256",
    )


def read_platform_operator_token(settings: Settings, token: str) -> PlatformOperatorClaims:
    try:
        payload = jwt.decode(
            token,
            _token_secret(settings),
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "scope", "exp", "iss"]},
        )
        if payload.get("scope") != "platform-owner":
            raise TokenError("Platform oturumu gerekli.")
        return PlatformOperatorClaims(
            user_id=UUID(str(payload["sub"])),
            expires_at=datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc),
        )
    except TokenError:
        raise
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise TokenError("Geçersiz veya süresi dolmuş platform oturumu.") from error


def _token_secret(settings: Settings) -> str:
    if not settings.token_signing_configured:
        raise TokenError("Merkezi API imzalama anahtarı yapılandırılmamış.")
    return str(settings.jwt_secret)


def _validate_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Parola en az 12 karakter olmalı.")
    if not any(character.isalpha() for character in password):
        raise ValueError("Parola en az bir harf içermeli.")
    if not any(character.isdigit() for character in password):
        raise ValueError("Parola en az bir rakam içermeli.")
