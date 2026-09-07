from __future__ import annotations

import pytest

from app.core.platform_connection import (
    PlatformApiClient,
    PlatformConnectionConfig,
    PlatformConnectionError,
    PlatformConnectionStore,
)


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
