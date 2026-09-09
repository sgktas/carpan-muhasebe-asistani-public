import asyncio
from uuid import uuid4

import httpx

from carpan_platform.api.dependencies import get_settings
from carpan_platform.config import Settings
from carpan_platform.main import create_app
from carpan_platform.management import Invitation, ManagementOverview, ManagementRepository
from carpan_platform.security import create_access_token


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url=None,
        jwt_secret="x" * 48,
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )


def _request(app, token: str):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(
                "/v1/management/overview",
                headers={"Authorization": f"Bearer {token}"},
            )

    return asyncio.run(send())


def _get(app, token: str, path: str):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path, headers={"Authorization": f"Bearer {token}"})

    return asyncio.run(send())


def _post(app, token: str, path: str, payload: dict):
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, headers={"Authorization": f"Bearer {token}"}, json=payload)

    return asyncio.run(send())


def test_management_overview_rejects_non_admin_before_data_access(monkeypatch):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    token = create_access_token(
        settings, user_id=uuid4(), company_id=uuid4(), role="OPERATOR"
    )

    def unexpected_overview(self, company_id):  # pragma: no cover - assertion guard
        raise AssertionError("Yönetici olmayan kullanıcı veri sorgusu yapmamalı.")

    monkeypatch.setattr(ManagementRepository, "overview", unexpected_overview)

    response = _request(app, token)

    assert response.status_code == 403
    assert response.json()["detail"] == "Bu merkezi yönetim işlemi için yetkiniz yok."


def test_management_overview_returns_tenant_scoped_summary(monkeypatch):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    company_id = uuid4()
    token = create_access_token(
        settings, user_id=uuid4(), company_id=company_id, role="ADMIN"
    )
    received_company_ids = []

    def overview(self, requested_company_id):
        received_company_ids.append(requested_company_id)
        return ManagementOverview(
            company_code="CARPAN",
            company_name="Çarpan Muhasebe Asistanı",
            company_status="ACTIVE",
            active_user_count=2,
            role_counts={"ADMIN": 1, "OPERATOR": 1},
            active_device_count=1,
            revoked_device_count=0,
            license_plan_code="PRO",
            license_status="ACTIVE",
            license_expires_at=None,
            enabled_modules=("MANIM", "FOM"),
        )

    monkeypatch.setattr(ManagementRepository, "overview", overview)

    response = _request(app, token)

    assert response.status_code == 200
    assert received_company_ids == [company_id]
    assert response.json() == {
        "company": {"code": "CARPAN", "name": "Çarpan Muhasebe Asistanı", "status": "ACTIVE"},
        "users": {"active_count": 2, "roles": {"ADMIN": 1, "OPERATOR": 1}},
        "devices": {"active_count": 1, "revoked_count": 0},
        "license": {
            "plan_code": "PRO",
            "status": "ACTIVE",
            "expires_at": None,
            "enabled_modules": ["MANIM", "FOM"],
        },
    }


def test_management_team_and_device_lists_are_admin_only(monkeypatch):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    company_id = uuid4()
    admin_token = create_access_token(settings, user_id=uuid4(), company_id=company_id, role="ADMIN")
    auditor_token = create_access_token(settings, user_id=uuid4(), company_id=company_id, role="AUDITOR")
    observed = []

    def team_members(self, requested_company_id):
        observed.append(("team", requested_company_id))
        return ()

    def devices(self, requested_company_id):
        observed.append(("devices", requested_company_id))
        return ()

    monkeypatch.setattr(ManagementRepository, "team_members", team_members)
    monkeypatch.setattr(ManagementRepository, "devices", devices)

    assert _get(app, auditor_token, "/v1/management/team").status_code == 403
    assert _get(app, auditor_token, "/v1/management/devices").status_code == 403
    assert _get(app, admin_token, "/v1/management/team").json() == {"members": []}
    assert _get(app, admin_token, "/v1/management/devices").json() == {"devices": []}
    assert observed == [("team", company_id), ("devices", company_id)]


def test_management_invitation_is_admin_only_and_returns_token_once(monkeypatch):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    company_id, user_id = uuid4(), uuid4()
    admin = create_access_token(settings, user_id=user_id, company_id=company_id, role="ADMIN")
    operator = create_access_token(settings, user_id=uuid4(), company_id=company_id, role="OPERATOR")
    observed = []

    def create_invitation(self, **payload):
        observed.append(payload)
        return Invitation(token="t" * 43, expires_at=None)

    monkeypatch.setattr(ManagementRepository, "create_invitation", create_invitation)

    async def post(token):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post("/v1/management/invitations", headers={"Authorization": f"Bearer {token}"}, json={"username":"new.user","display_name":"Yeni Kullanıcı","role":"OPERATOR"})

    assert asyncio.run(post(operator)).status_code == 403
    response = asyncio.run(post(admin))
    assert response.status_code == 201
    assert response.json()["invite_token"] == "t" * 43
    assert observed == [{"company_id": company_id, "actor_user_id": user_id, "username": "new.user", "display_name": "Yeni Kullanıcı", "role": "OPERATOR"}]


def test_management_device_revocation_is_admin_only_and_scoped(monkeypatch):
    settings = _settings()
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    company_id, user_id = uuid4(), uuid4()
    admin = create_access_token(settings, user_id=user_id, company_id=company_id, role="ADMIN")
    operator = create_access_token(settings, user_id=uuid4(), company_id=company_id, role="OPERATOR")
    observed = []

    def revoke_device(self, **payload):
        observed.append(payload)
        return 1

    monkeypatch.setattr(ManagementRepository, "revoke_device", revoke_device)
    payload = {"assigned_username": "operator.1", "device_label": "Muhasebe PC"}

    assert _post(app, operator, "/v1/management/devices/revoke", payload).status_code == 403
    assert _post(app, admin, "/v1/management/devices/revoke", payload).status_code == 204
    assert observed == [{
        "company_id": company_id,
        "actor_user_id": user_id,
        "assigned_username": "operator.1",
        "device_label": "Muhasebe PC",
    }]
