"""Merkezi yönetim panelinin statik kabuğu.

Panel yalnız merkezi API ile konuşur; banka, Excel veya müşteri dosyalarını
tarayıcıya ya da sunucuya taşımaz.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


WEB_ROOT = Path(__file__).resolve().parent / "web"
router = APIRouter(include_in_schema=False)


@router.get("/admin")
def admin_panel() -> FileResponse:
    response = FileResponse(WEB_ROOT / "admin.html", media_type="text/html")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
        "connect-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/platform")
def platform_owner_panel() -> FileResponse:
    """Firma yönetiminden ayrı platform sahibi paneli."""
    response = FileResponse(WEB_ROOT / "platform.html", media_type="text/html")
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
        "connect-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/invite")
def invitation_panel() -> FileResponse:
    response = FileResponse(WEB_ROOT / "invite.html", media_type="text/html")
    response.headers["Content-Security-Policy"] = "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; connect-src 'self'; script-src 'self'; style-src 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
