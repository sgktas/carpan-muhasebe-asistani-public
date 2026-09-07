from app.core.installation_identity import InstallationIdentityStore


def test_installation_identity_is_random_and_persistent(tmp_path):
    store = InstallationIdentityStore(tmp_path)

    first = store.get_or_create()

    assert len(first) >= 16
    assert InstallationIdentityStore(tmp_path).get_or_create() == first
    assert "installation_id" in (tmp_path / "installation_identity.json").read_text(
        encoding="utf-8"
    )
