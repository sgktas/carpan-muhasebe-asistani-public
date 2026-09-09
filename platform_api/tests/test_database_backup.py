import hashlib

import pytest

from scripts.database_backup import database_target, file_sha256


def test_database_target_parses_connection_without_exposing_it():
    target = database_target("postgresql://backup_user:secret@127.0.0.1:5432/carpan_platform")

    assert (target.host, target.port, target.database, target.user) == (
        "127.0.0.1", "5432", "carpan_platform", "backup_user"
    )
    assert target.password == "secret"


def test_database_target_rejects_incomplete_connection():
    with pytest.raises(ValueError):
        database_target("postgresql://localhost/carpan_platform")


def test_file_sha256_reads_a_backup_file(tmp_path):
    backup = tmp_path / "database.dump"
    backup.write_bytes(b"carpan-backup")

    assert file_sha256(backup) == hashlib.sha256(b"carpan-backup").hexdigest()
