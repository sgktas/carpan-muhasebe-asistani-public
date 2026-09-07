from __future__ import annotations

from app.core.company_workspace import CompanyWorkspaceManager


def test_company_workspace_copies_legacy_state_without_moving_identity(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "customer_mappings.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data" / "platform.sqlite3").write_bytes(b"identity")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "bolge_kodlari.json").write_text("{}", encoding="utf-8")

    workspace = CompanyWorkspaceManager(tmp_path).prepare(7, migrate_legacy=True)

    assert workspace.migrated_legacy_data
    assert (workspace.root / "data" / "customer_mappings.json").is_file()
    assert not (workspace.root / "data" / "platform.sqlite3").exists()
    assert (tmp_path / "data" / "customer_mappings.json").is_file()
    assert (workspace.root / "config" / "bolge_kodlari.json").is_file()


def test_second_company_starts_isolated_without_legacy_copy(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "customer_mappings.json").write_text("{}", encoding="utf-8")

    workspace = CompanyWorkspaceManager(tmp_path).prepare(8, migrate_legacy=False)

    assert not workspace.migrated_legacy_data
    assert not (workspace.root / "data" / "customer_mappings.json").exists()
