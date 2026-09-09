"""Merkezi API için ortak oturum ve rol bağımlılıkları."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from carpan_platform.config import Settings
from carpan_platform.security import AccessTokenClaims, TokenError, read_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_settings() -> Settings:
    return Settings.from_environment()


def current_claims(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AccessTokenClaims:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Giriş gerekli.")
    try:
        return read_access_token(settings, credentials.credentials)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum geçersiz.") from None


def require_roles(*roles: str) -> Callable[[AccessTokenClaims], AccessTokenClaims]:
    allowed = frozenset(str(role).strip().upper() for role in roles if str(role).strip())
    if not allowed:
        raise ValueError("En az bir rol tanımlanmalı.")

    def dependency(claims: AccessTokenClaims = Depends(current_claims)) -> AccessTokenClaims:
        if claims.role.upper() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu merkezi yönetim işlemi için yetkiniz yok.",
            )
        return claims

    return dependency
