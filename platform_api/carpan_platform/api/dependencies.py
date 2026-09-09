"""Merkezi API için ortak oturum ve rol bağımlılıkları."""
from __future__ import annotations

from collections.abc import Callable

from dataclasses import replace

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import psycopg

from carpan_platform.config import Settings
from carpan_platform.database import tenant_transaction
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
        claims = read_access_token(settings, credentials.credentials)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum geçersiz.") from None
    # Merkezi veritabanı varsa token tek başına yeterli değildir: pasife alınan
    # kullanıcı veya değişmiş rol, bir sonraki korumalı istekte uygulanır.
    if not settings.database_configured:
        return claims
    try:
        with tenant_transaction(settings, claims.company_id) as connection:
            row = connection.execute(
                """
                SELECT m.role
                FROM carpan.company_memberships m
                JOIN carpan.users u ON u.id=m.user_id
                JOIN carpan.companies c ON c.id=m.company_id
                WHERE m.company_id=%s AND m.user_id=%s
                  AND m.active AND u.status='ACTIVE' AND c.status='ACTIVE'
                """,
                (claims.company_id, claims.user_id),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Merkezi erişim artık etkin değil.")
        return replace(claims, role=str(row["role"]))
    except HTTPException:
        raise
    except (psycopg.Error, OSError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Merkezi oturum doğrulanamadı.") from None


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
