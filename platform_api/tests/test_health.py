import asyncio

import httpx

from carpan_platform.api.auth import get_settings
from carpan_platform.config import Settings
from carpan_platform.main import create_app
from carpan_platform.security import create_access_token
from uuid import uuid4


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


def test_login_is_unavailable_until_central_database_is_configured():
    settings = Settings(
        environment="test",
        database_url=None,
        jwt_secret=None,
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    async def login():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/v1/auth/login",
                json={"company_code": "CARPAN", "username": "admin", "password": "test"},
            )

    response = asyncio.run(login())

    assert response.status_code == 503


def test_me_accepts_a_valid_company_scoped_token():
    settings = Settings(
        environment="test",
        database_url=None,
        jwt_secret="x" * 48,
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    user_id = uuid4()
    company_id = uuid4()
    token = create_access_token(
        settings,
        user_id=user_id,
        company_id=company_id,
        role="ADMIN",
    )

    async def get_me():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    response = asyncio.run(get_me())

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(user_id),
        "company_id": str(company_id),
        "role": "ADMIN",
    }
