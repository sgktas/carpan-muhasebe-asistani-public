import asyncio

import httpx

from carpan_platform.config import Settings
from carpan_platform.main import create_app


def test_admin_panel_is_served_with_browser_security_headers():
    app = create_app(
        Settings(environment="test", database_url=None, jwt_secret=None, jwt_issuer="test", allowed_origins=())
    )

    async def fetch():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/admin")

    response = asyncio.run(fetch())

    assert response.status_code == 200
    assert "Çarpan | Yönetim Merkezi" in response.text
    assert "Content-Security-Policy" in response.headers
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
