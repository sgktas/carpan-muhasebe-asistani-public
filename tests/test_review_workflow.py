import sqlite3
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from app.core import identity
from app.core.identity import IdentityStore, IdentityError
from app.core.review_queue import ReviewQueue, ReviewMember, ReviewQueueError
from app.core.review_workflow import ReviewWorkflow


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "PASSWORD_ITERATIONS", 1000)
    store = IdentityStore(tmp_path / "identity.db")
    admin = store.create_initial_admin("Demo", "admin", "Yönetici", "Guvenli1234")
    sessions = {"admin": admin}
    for name, role in [("operator", "OPERATOR"), ("other", "OPERATOR"), ("approver", "APPROVER"), ("auditor", "AUDITOR")]:
        store.create_user(admin, username=name, display_name=name, password="Guvenli1234", role=role)
        sessions[name] = store.authenticate(name, "Guvenli1234", admin.company_id)
    queue = ReviewQueue(tmp_path / "operations.db", company_id=admin.company_id)
    group = queue.enqueue([ReviewMember("demo.xlsx", 2, 70978, "ANTALYA", "GARANTI", "fark"), ReviewMember("demo.xlsx", 3, 77000, "ANTALYA", "GARANTI", "fark")])
    services = {name: ReviewWorkflow(queue, store, session) for name, session in sessions.items()}
    return store, sessions, queue, group, services


def act(service, group, action, **kwargs):
    task = next(t for t in service.list() if t.group.group_id == group)
    service.act(group, action, expected_version=task.group.version, **kwargs)


def test_full_flow_owner_and_actor_are_separate_and_sources_survive(system):
    store, sessions, queue, group, services = system
    deadline = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    act(services["admin"], group, "assign", target_user_id=sessions["operator"].user_id, due_at=deadline)
    task = services["operator"].list()[0]
    assert task.overdue
    assert task.group.total_amount == 147978
    assert len(task.group.members) == 2
    event = services["admin"].events(group)[0]
    assert event["actor_user_id"] == sessions["admin"].user_id
    assert json.loads(event["payload"])["owner"] == sessions["operator"].user_id
    with pytest.raises(ReviewQueueError):
        act(services["other"], group, "start")
    act(services["operator"], group, "start")
    act(services["operator"], group, "submit", decision="HAVALE", note="Toplamlar kontrol edildi")
    with pytest.raises(ReviewQueueError):
        act(services["operator"], group, "approve", note="onay")
    act(services["approver"], group, "reject", note="Kaynak tarihi tekrar kontrol edilmeli")
    act(services["operator"], group, "start")
    act(services["operator"], group, "submit", decision="HAVALE", note="Tarih doğrulandı")
    act(services["approver"], group, "approve", note="İncelendi")
    task = services["admin"].list()[0]
    assert task.phase == "APPROVED" and not task.overdue
    assert task.group.assigned_user_id == sessions["operator"].user_id
    assert services["admin"].audit_valid()
    act(services["admin"], group, "reopen", note="Yeni bilgi geldi")
    assert services["admin"].list()[0].group.assigned_user_id is None


def test_auditor_cannot_mutate_and_revoked_session_stops_immediately(system):
    store, sessions, queue, group, services = system
    assert services["auditor"].list()
    for action in ("claim", "assign", "start", "submit", "approve", "reject", "reopen"):
        with pytest.raises(ReviewQueueError):
            act(services["auditor"], group, action, note="test", decision="HAVALE")
    store.update_member(sessions["admin"], sessions["operator"].user_id, role="OPERATOR", active=False)
    with pytest.raises(IdentityError):
        services["operator"].list()
    with pytest.raises(ReviewQueueError):
        act(services["admin"], group, "assign", target_user_id=sessions["operator"].user_id)
    with pytest.raises(ReviewQueueError):
        act(services["admin"], group, "assign", target_user_id=sessions["auditor"].user_id)


def test_region_filter_hides_entire_mixed_group_and_prevents_actions(system):
    store, sessions, queue, group, services = system
    mixed = queue.enqueue([ReviewMember("a", 1, 1, "ANTALYA", "GARANTI", ""), ReviewMember("b", 2, 2, "AYDIN", "GARANTI", "")])
    store.set_review_regions(sessions["admin"], sessions["operator"].user_id, ["ANTALYA"])
    assert [t.group.group_id for t in services["operator"].list()] == [group]
    with pytest.raises(ReviewQueueError):
        services["operator"].act(mixed, "claim", expected_version=1)
    with pytest.raises(ReviewQueueError):
        services["operator"].events(mixed)
    with pytest.raises(ReviewQueueError):
        act(services["admin"], mixed, "assign", target_user_id=sessions["operator"].user_id)
    assert store.audit_chain_is_valid()


def test_company_scope_and_forged_role_are_rejected(system):
    store, sessions, queue, group, services = system
    fake = replace(sessions["operator"], role="ADMIN")
    service = ReviewWorkflow(queue, store, fake)
    with pytest.raises(ReviewQueueError):
        act(service, group, "assign", target_user_id=sessions["other"].user_id)
    with pytest.raises(IdentityError):
        ReviewWorkflow(queue, store, replace(fake, company_id=999))


def test_concurrent_claim_has_exactly_one_winner(system):
    _, _, queue, group, services = system
    def claim(name):
        try:
            services[name].act(group, "claim", expected_version=1)
            return True
        except ReviewQueueError:
            return False
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(claim, ["operator", "other"]))
    assert sum(results) == 1
    assert len(services["admin"].events(group)) == 1


def test_audit_cannot_be_edited_and_legacy_mutations_cannot_bypass_service(system):
    _, _, queue, group, services = system
    act(services["operator"], group, "claim")
    with queue._connection() as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("DELETE FROM review_workflow_audit")
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("UPDATE review_workflow_audit SET action='approve'")
    with pytest.raises(ReviewQueueError):
        queue.resolve(group, user_id=1, resolution_code="HAVALE")
    assert services["admin"].audit_valid()


def test_required_notes_and_state_transitions_do_not_write_on_failure(system):
    _, _, _, group, services = system
    act(services["operator"], group, "claim")
    act(services["operator"], group, "start")
    for kwargs in [{"decision": "HAVALE"}, {"decision": "INVALID", "note": "a"}]:
        with pytest.raises(ReviewQueueError):
            act(services["operator"], group, "submit", **kwargs)
    assert len(services["operator"].events(group)) == 2
    assert services["operator"].list()[0].phase == "IN_REVIEW"


def test_single_admin_can_complete_with_explicit_self_approval_audit(system):
    _, _, _, group, services = system
    service = services["admin"]
    act(service, group, "claim")
    act(service, group, "start")
    act(service, group, "submit", decision="SOURCE_CORRECTED", note="Kontrol edildi")
    act(service, group, "approve", note="Tek kullanıcı olarak onaylandı")
    assert json.loads(service.events(group)[-1]["payload"])["self_approval"] is True


def test_approval_owner_cannot_self_approve_without_admin_authority(system):
    _, _, _, group, services = system
    act(services["approver"], group, "claim")
    act(services["approver"], group, "start")
    act(services["approver"], group, "submit", decision="HAVALE", note="Kontrol")
    with pytest.raises(ReviewQueueError):
        act(services["approver"], group, "approve", note="Kendi kararım")
    act(services["admin"], group, "approve", note="İkinci kontrol")


def test_audit_failure_rolls_back_entire_transition(system, monkeypatch):
    _, _, queue, group, services = system
    def fail(*args):
        raise RuntimeError("disk write failed")
    monkeypatch.setattr(queue, "_add_event", fail)
    with pytest.raises(RuntimeError):
        act(services["operator"], group, "claim")
    task = services["admin"].list()[0]
    assert task.phase == "OPEN" and task.group.version == 1
    assert services["admin"].events(group) == []


def test_legacy_queue_is_migrated_without_losing_members(system, tmp_path):
    store, sessions, _, _, _ = system
    queue = ReviewQueue(tmp_path / "legacy.db", company_id=sessions["admin"].company_id)
    group = queue.enqueue([ReviewMember("old.xlsx", 9, 125, "AYDIN", "GARANTI", "eski")])
    queue.resolve(group, user_id=sessions["admin"].user_id, resolution_code="HAVALE")
    workflow = ReviewWorkflow(queue, store, sessions["admin"])
    task = workflow.list()[0]
    assert task.phase == "APPROVED"
    assert task.decision == "HAVALE"
    assert task.group.members[0].source_row == 9
    act(workflow, group, "reopen", note="Yeniden incele")
    assert workflow.list()[0].phase == "OPEN"
