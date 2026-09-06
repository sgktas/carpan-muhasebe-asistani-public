import asyncio

import httpx

from carpan_platform.config import Settings
from carpan_platform.main import create_app


def test_health_is_available_before_database_deployment():
    app = create_app(
        Settings(
            environment="test",
            database_url=None,
            jwt_secret=None,
            jwt_issuer="carpan-test",
            allowed_origins=(),
        )
    )

    async def get_health():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/health")

    response = asyncio.run(get_health())

    assert response.status_code == 200
    assert response.json() == {
        "service": "carpan-platform-api",
        "environment": "test",
        "status": "ok",
        "database": "not-configured",
    }
