from __future__ import annotations

import pytest
from urllib.error import HTTPError, URLError

from app.core.platform_connection import (
    PlatformApiClient,
    PlatformAuthenticationError,
    PlatformConnectionConfig,
    PlatformConnectionError,
    PlatformConnectionStore,
)
from app.core.platform_session import PlatformSessionError


class _Response:
    status = 200

    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._payload


def test_platform_url_requires_https_except_local_development(tmp_path):
    store = PlatformConnectionStore(tmp_path)
    with pytest.raises(PlatformConnectionError, match="HTTPS"):
        store.save("http://platform.carpan.example")

    saved = store.save("https://platform.carpan.example/")
    assert saved.api_url == "https://platform.carpan.example"
    assert PlatformConnectionStore(tmp_path).get() == saved


def test_platform_url_is_canonical_and_rejects_credentials_or_query(tmp_path):
    assert PlatformConnectionConfig("https://PLATFORM.CARPAN.EXAMPLE/central/").api_url == "https://platform.carpan.example/central"
    with pytest.raises(PlatformConnectionError):
        PlatformConnectionStore(tmp_path).save("https://username" + ":password" + "@platform.carpan.example")
    with pytest.raises(PlatformSessionError):
        PlatformConnectionConfig("https://platform.carpan.example/?secret=value")


def test_platform_health_is_offline_safe_and_never_needs_database_access():
    local = PlatformApiClient(PlatformConnectionConfig())
    assert local.health().state == "not_configured"

    client = PlatformApiClient(
        PlatformConnectionConfig("https://platform.carpan.example"),
        opener=lambda _request, timeout: _Response(
            b'{"service":"carpan-platform-api","status":"ok"}'
        ),
    )
    assert client.health().is_connected


def test_platform_login_uses_https_json_and_returns_only_a_valid_session():
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = request.data
        captured["authorization"] = request.get_header("Authorization")
        assert timeout == 8.0
        return _Response(
            b'{"access_token":"aaaaaaaaaaaaaaaa","refresh_token":"refresh-token-rrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrr","display_name":"Yonetic i","role":"ADMIN"}'
        )

    client = PlatformApiClient(PlatformConnectionConfig("https://platform.carpan.example"), opener=opener)
    session = client.login(company_code="CARPAN", username="yonetici", password="gizli-parola")

    assert session.api_url == "https://platform.carpan.example"
    assert captured["url"].endswith("/v1/auth/login")
    assert b"gizli-parola" in captured["payload"]
    assert captured["authorization"] is None


def test_platform_authentication_error_never_echoes_secret_values():
    client = PlatformApiClient(
        PlatformConnectionConfig("https://platform.carpan.example"),
        opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )

    with pytest.raises(PlatformAuthenticationError) as error:
        client.refresh("refresh-secret-value")

    assert "refresh-secret-value" not in str(error.value)


def test_default_client_does_not_follow_redirects_with_credentials(monkeypatch):
    client = PlatformApiClient(PlatformConnectionConfig("https://platform.carpan.example"))
    redirect = HTTPError("https://platform.carpan.example/v1/auth/refresh", 302, "redirect", {}, None)
    monkeypatch.setattr(client, "_opener", lambda *_args, **_kwargs: (_ for _ in ()).throw(redirect))
    with pytest.raises(PlatformAuthenticationError):
        client.refresh("refresh-secret-value")


def test_platform_license_uses_authorized_api_contract():
    captured = {}

    def opener(request, timeout):
        captured["method"] = request.get_method()
        captured["authorization"] = request.get_header("Authorization")
        return _Response(b'{"plan_code":"PRO","status":"ACTIVE","expires_at":null,"enabled_modules":["manim_transfer"],"usable":true}')

    license_info = PlatformApiClient(PlatformConnectionConfig("https://platform.carpan.example"), opener=opener).license("access-token")

    assert captured == {"method": "GET", "authorization": "Bearer access-token"}
    assert license_info.usable
    assert license_info.enabled_modules == {"manim_transfer"}
