from datetime import datetime, timezone
from uuid import uuid4

import pytest

from carpan_platform.config import Settings
from carpan_platform.security import (
    TokenError,
    create_access_token,
    hash_password,
    read_access_token,
    verify_password,
)


@pytest.fixture
def settings():
    return Settings(
        environment="test",
        database_url=None,
        jwt_secret="x" * 48,
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )


def test_passwords_are_argon2_hashed_and_verified():
    password_hash = hash_password("MerkeziParola123")

    assert password_hash != "MerkeziParola123"
    assert verify_password("MerkeziParola123", password_hash)
    assert not verify_password("yanlis", password_hash)


def test_access_token_carries_company_scope(settings):
    user_id = uuid4()
    company_id = uuid4()
    token = create_access_token(
        settings,
        user_id=user_id,
        company_id=company_id,
        role="ADMIN",
        now=datetime.now(timezone.utc),
    )

    claims = read_access_token(settings, token)

    assert claims.user_id == user_id
    assert claims.company_id == company_id
    assert claims.role == "ADMIN"


def test_token_cannot_be_read_with_a_different_signing_key(settings):
    token = create_access_token(
        settings,
        user_id=uuid4(),
        company_id=uuid4(),
        role="AUDITOR",
    )
    other_settings = Settings(
        environment="test",
        database_url=None,
        jwt_secret="y" * 48,
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )

    with pytest.raises(TokenError):
        read_access_token(other_settings, token)
