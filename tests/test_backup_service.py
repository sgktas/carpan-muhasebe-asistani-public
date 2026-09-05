from pathlib import Path
import zipfile

from app.core.backup_service import create_local_backup


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
    assert "CarpanMuhasebeAsistani/logs/uygulama.log" not in names
