from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.configuration_change_audit import (
    ConfigurationChangeAudit,
    ConfigurationChangeConflict,
)


def audit(tmp_path, *, company_id=1, user_id=10, actor="Yönetici"):
    return ConfigurationChangeAudit(
        tmp_path / "operations.sqlite3", company_id=company_id,
        user_id=user_id, actor=actor,
    )


def test_change_has_per_subject_revision_previous_new_and_actor(tmp_path):
    changes = audit(tmp_path)
    first = changes.record(
        "active_profile:output", before={"profile_id": "netsis"},
        after={"profile_id": "netsis_toplu"},
    )
    second = changes.record(
        "active_profile:output", before={"profile_id": "netsis_toplu"},
        after={"profile_id": "netsis"}, expected_fingerprint=first.after_fingerprint,
    )
    assert first.revision == 1
    assert second.revision == 2
    assert second.actor == "Yönetici"
    assert changes.recent() == [second, first]


def test_unchanged_value_never_creates_an_audit_row(tmp_path):
    changes = audit(tmp_path)
    assert changes.record("regions", before={"BODRUM": {}}, after={"BODRUM": {}}) is None
    assert changes.recent() == []


def test_stale_settings_window_is_rejected_without_creating_a_new_revision(tmp_path):
    first_window = audit(tmp_path, actor="İlk kullanıcı")
    second_window = audit(tmp_path, actor="İkinci kullanıcı")
    created = first_window.record(
        "regions", before={"BODRUM": {"kasa": 1}}, after={"BODRUM": {"kasa": 2}},
    )
    with pytest.raises(ConfigurationChangeConflict, match="başka bir açık pencerede"):
        second_window.record(
            "regions", before={"BODRUM": {"kasa": 1}}, after={"BODRUM": {"kasa": 3}},
            expected_fingerprint=None,
        )
    # First event remains the only source of truth. A fresh editor may continue.
    assert first_window.recent() == [created]
    continued = second_window.record(
        "regions", before={"BODRUM": {"kasa": 2}}, after={"BODRUM": {"kasa": 3}},
        expected_fingerprint=created.after_fingerprint,
    )
    assert continued.revision == 2


def test_company_scope_and_local_only_payloads_are_kept_separate(tmp_path):
    first = audit(tmp_path, company_id=1, actor="Firma 1")
    second = audit(tmp_path, company_id=2, actor="Firma 2")
    first.record("regions", before={"code": "A"}, after={"code": "B"})
    second.record("regions", before={"code": "A"}, after={"code": "C"})
    assert first.recent()[0].after == {"code": "B"}
    assert second.recent()[0].after == {"code": "C"}
    assert first.recent()[0].revision == second.recent()[0].revision == 1


def test_parallel_changes_receive_one_ordered_revision_sequence(tmp_path):
    path = tmp_path / "operations.sqlite3"

    def create(index):
        changes = ConfigurationChangeAudit(path, company_id=1, user_id=index, actor=f"K{index}")
        return changes.record(
            f"profile:input:{index}", before={"value": 0}, after={"value": index + 1},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(create, range(8)))
    assert all(change.revision == 1 for change in created)
    assert len(audit(tmp_path).recent()) == 8


def test_fingerprint_is_canonical_and_values_cannot_be_mutated_after_record(tmp_path):
    changes = audit(tmp_path)
    before = {"b": 2, "a": ["x"]}
    after = {"b": 3, "a": ["x"]}
    event = changes.record("profiles", before=before, after=after)
    before["a"].append("changed")
    after["b"] = 4
    restored = changes.recent()[0]
    assert restored.before == {"a": ["x"], "b": 2}
    assert restored.after == {"a": ["x"], "b": 3}
    assert ConfigurationChangeAudit.fingerprint({"a": ["x"], "b": 2}) == event.before_fingerprint
