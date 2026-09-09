from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str | None
    jwt_secret: str | None
    jwt_issuer: str
    allowed_origins: tuple[str, ...]
    owner_database_url: str | None = None

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def token_signing_configured(self) -> bool:
        secret = self.jwt_secret or ""
        return len(secret) >= 32 and not secret.startswith("CHANGE_ME")

    @property
    def platform_owner_configured(self) -> bool:
        """Firma dışı platform yönetimi için ayrı, yalnız sunucudaki bağlantı."""
        return bool(self.owner_database_url and self.token_signing_configured)

    @classmethod
    def from_environment(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv("CARPAN_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        )
        return cls(
            environment=os.getenv("CARPAN_ENVIRONMENT", "development").strip(),
            database_url=os.getenv("CARPAN_DATABASE_URL") or None,
            jwt_secret=os.getenv("CARPAN_JWT_SECRET") or None,
            jwt_issuer=os.getenv("CARPAN_JWT_ISSUER", "carpan-platform").strip(),
            allowed_origins=origins,
            owner_database_url=os.getenv("CARPAN_OWNER_DATABASE_URL") or None,
        )
