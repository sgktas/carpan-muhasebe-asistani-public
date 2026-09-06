from carpan_platform.config import Settings


def test_settings_marks_incomplete_central_configuration():
    settings = Settings(
        environment="test",
        database_url=None,
        jwt_secret="short",
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )

    assert not settings.database_configured
    assert not settings.token_signing_configured


def test_settings_reads_multiple_allowed_origins(monkeypatch):
    monkeypatch.setenv("CARPAN_ALLOWED_ORIGINS", "https://app.example.test, https://admin.example.test")
    settings = Settings.from_environment()

    assert settings.allowed_origins == (
        "https://app.example.test",
        "https://admin.example.test",
    )


def test_example_placeholder_cannot_enable_token_signing():
    settings = Settings(
        environment="production",
        database_url="postgresql://example",
        jwt_secret="CHANGE_ME_WITH_A_LONG_RANDOM_SECRET_VALUE",
        jwt_issuer="carpan-platform",
        allowed_origins=(),
    )

    assert not settings.token_signing_configured
