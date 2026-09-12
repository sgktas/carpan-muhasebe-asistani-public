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
    monkeypatch.setattr(preflight_deployment, "server_capacity_ready", lambda: (True, "Sunucu kapasitesi"))
    monkeypatch.setattr(preflight_deployment, "api_port_available", lambda: True)

    assert preflight_deployment.main() == 1
    output = capsys.readouterr().out
    assert "OK: Veritabanı ve migrasyonlar" in output
    assert "HATA: Platform sahibi bağlantısı ve migrasyonlar" in output
    assert "Dağıtım durduruldu" in output


def test_preflight_accepts_only_when_both_database_connections_are_ready(monkeypatch, capsys):
    monkeypatch.setattr(preflight_deployment.Settings, "from_environment", classmethod(lambda cls: _settings()))
    monkeypatch.setattr(preflight_deployment, "database_schema_ready", lambda settings: True)
    monkeypatch.setattr(preflight_deployment, "owner_database_schema_ready", lambda settings: True)
    monkeypatch.setattr(preflight_deployment, "server_capacity_ready", lambda: (True, "Sunucu kapasitesi"))
    monkeypatch.setattr(preflight_deployment, "api_port_available", lambda: True)

    assert preflight_deployment.main() == 0
    assert "Merkezi API dağıtıma hazır." in capsys.readouterr().out


def test_preflight_stops_when_server_capacity_is_not_enough(monkeypatch, capsys):
    monkeypatch.setattr(preflight_deployment.Settings, "from_environment", classmethod(lambda cls: _settings()))
    monkeypatch.setattr(preflight_deployment, "server_capacity_ready", lambda: (False, "Sunucu kapasitesi: RAM 1.8 GB"))
    monkeypatch.setattr(preflight_deployment, "api_port_available", lambda: True)
    monkeypatch.setattr(preflight_deployment, "database_schema_ready", lambda settings: True)
    monkeypatch.setattr(preflight_deployment, "owner_database_schema_ready", lambda settings: True)

    assert preflight_deployment.main() == 1
    assert "HATA: Sunucu kapasitesi: RAM 1.8 GB" in capsys.readouterr().out


def test_preflight_stops_when_api_port_is_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(preflight_deployment.Settings, "from_environment", classmethod(lambda cls: _settings()))
    monkeypatch.setattr(preflight_deployment, "server_capacity_ready", lambda: (True, "Sunucu kapasitesi"))
    monkeypatch.setattr(preflight_deployment, "api_port_available", lambda: False)
    monkeypatch.setattr(preflight_deployment, "database_schema_ready", lambda settings: True)
    monkeypatch.setattr(preflight_deployment, "owner_database_schema_ready", lambda settings: True)

    assert preflight_deployment.main() == 1
    assert "HATA: Yerel API portu 8010" in capsys.readouterr().out
