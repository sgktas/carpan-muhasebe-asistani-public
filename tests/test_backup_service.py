from pathlib import Path
import zipfile

import pytest

from app.core.backup_service import (
    BackupError,
    create_local_backup,
    restore_local_backup,
    validate_local_backup,
)


def test_local_backup_contains_state_but_not_logs(tmp_path):
    data_root = tmp_path / "data-root"
    (data_root / "data").mkdir(parents=True)
    (data_root / "config").mkdir()
    (data_root / "logs").mkdir()
    (data_root / "data" / "history.db").write_bytes(b"sqlite-test")
    (data_root / "config" / "profile.json").write_text("{}", encoding="utf-8")
    (data_root / "logs" / "uygulama.log").write_text("secret", encoding="utf-8")
    destination = tmp_path / "backup.zip"

    created = create_local_backup(data_root, destination)

    assert created == destination
    with zipfile.ZipFile(created) as archive:
        names = set(archive.namelist())
    assert "CarpanMuhasebeAsistani/data/history.db" in names
    assert "CarpanMuhasebeAsistani/config/profile.json" in names
    assert "CarpanMuhasebeAsistani/YEDEK_BILGISI.txt" in names
    assert "CarpanMuhasebeAsistani/YEDEK_MANIFEST.json" in names
    assert "CarpanMuhasebeAsistani/logs/uygulama.log" not in names
    assert validate_local_backup(created)["version"] == 1


def test_local_backup_detects_tampered_file(tmp_path):
    data_root = tmp_path / "data-root"
    data_root.mkdir()
    (data_root / "state.json").write_text("original", encoding="utf-8")
    destination = tmp_path / "backup.zip"
    create_local_backup(data_root, destination)

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(destination) as source, zipfile.ZipFile(tampered, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.endswith("state.json"):
                data = b"changed"
            target.writestr(item, data)

    with pytest.raises(BackupError, match="bozulmuş"):
        validate_local_backup(tampered)


def test_local_backup_restore_keeps_previous_data_as_rollback(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "new.json").write_text("new", encoding="utf-8")
    backup = tmp_path / "backup.zip"
    create_local_backup(source, backup)

    target = tmp_path / "target"
    target.mkdir()
    (target / "old.json").write_text("old", encoding="utf-8")
    rollback = restore_local_backup(backup, target)

    assert rollback is not None
    assert (target / "new.json").read_text(encoding="utf-8") == "new"
    assert (rollback / "old.json").read_text(encoding="utf-8") == "old"
