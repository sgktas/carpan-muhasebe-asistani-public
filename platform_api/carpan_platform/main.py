from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from carpan_platform.api.auth import router as auth_router
from carpan_platform.api.licensing import router as licensing_router
from carpan_platform.api.invitations import router as invitations_router
from carpan_platform.api.management import router as management_router
from carpan_platform.config import Settings
from carpan_platform.database import database_health
from carpan_platform.web_ui import WEB_ROOT, router as web_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    app = FastAPI(
        title="Çarpan Merkezi Platform API",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
    )
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Device-Id"],
        )
    app.include_router(auth_router)
    app.include_router(licensing_router)
    app.include_router(invitations_router)
    app.include_router(management_router)
    app.include_router(web_router)
    app.mount("/admin/assets", StaticFiles(directory=WEB_ROOT), name="admin-assets")

    @app.get("/health", tags=["system"])
    def health() -> dict[str, object]:
        database_ok = database_health(settings)
        return {
            "service": "carpan-platform-api",
            "environment": settings.environment,
            "status": "ok" if not settings.database_configured or database_ok else "degraded",
            "database": "connected" if database_ok else "not-configured",
        }

    return app


app = create_app()
