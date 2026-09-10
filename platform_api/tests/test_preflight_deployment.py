from carpan_platform.config import Settings
from scripts import preflight_deployment


def _settings() -> Settings:
    return Settings(
        environment="test",
        database_url="postgresql://app:test@127.0.0.1:5432/carpan_platform",
        owner_database_url="postgresql://owner:test@127.0.0.1:5432/carpan_platform",
        jwt_secret="x" * 48,
        jwt_issuer="carpan-test",
        allowed_origins=(),
    )


def test_preflight_requires_owner_connection_schema_before_deployment(monkeypatch, capsys):
    monkeypatch.setattr(preflight_deployment.Settings, "from_environment", classmethod(lambda cls: _settings()))
    monkeypatch.setattr(preflight_deployment, "database_schema_ready", lambda settings: True)
    monkeypatch.setattr(preflight_deployment, "owner_database_schema_ready", lambda settings: False)

    assert preflight_deployment.main() == 1
    output = capsys.readouterr().out
    assert "OK: Veritabanı ve migrasyonlar" in output
    assert "HATA: Platform sahibi bağlantısı ve migrasyonlar" in output
    assert "Dağıtım durduruldu" in output


def test_preflight_accepts_only_when_both_database_connections_are_ready(monkeypatch, capsys):
    monkeypatch.setattr(preflight_deployment.Settings, "from_environment", classmethod(lambda cls: _settings()))
    monkeypatch.setattr(preflight_deployment, "database_schema_ready", lambda settings: True)
    monkeypatch.setattr(preflight_deployment, "owner_database_schema_ready", lambda settings: True)

    assert preflight_deployment.main() == 0
    assert "Merkezi API dağıtıma hazır." in capsys.readouterr().out
