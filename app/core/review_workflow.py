"""Local review service: identity, ownership, version and audit checked together.

Approval closes an operational review only; it never publishes an ERP entry.
Legacy queue identities and source members remain unchanged.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from app.core.identity import AuthenticatedSession, IdentityError, IdentityStore
from app.core.review_queue import ReviewQueue, ReviewQueueError

PHASE_LABELS = {
    "OPEN": "Bekliyor", "ASSIGNED": "Atandı", "IN_REVIEW": "İnceleniyor",
    "PENDING_APPROVAL": "Onay bekliyor", "APPROVED": "Onaylandı",
    "REJECTED": "İade edildi", "CANCELLED": "İptal edildi",
}
DECISIONS = {"HAVALE": "Havale", "REFERANSLI": "Referanslı kayıt", "ODEME_ONAYLANDI": "Ödeme onaylandı", "VIRMAN": "Aynı banka virmanı", "SOURCE_CORRECTED": "Kaynak düzeltildi", "NO_ACTION": "İşlem gerekmiyor"}


@dataclass(frozen=True)
class ReviewTask:
    group: object
    phase: str
    due_at: str | None
    submitted_by: int | None
    decision: str | None
    note: str

    @property
    def overdue(self):
        return bool(self.due_at and self.phase not in {"APPROVED", "CANCELLED"}
                    and datetime.fromisoformat(self.due_at) < datetime.now(timezone.utc))


class ReviewWorkflow:
    def __init__(self, queue: ReviewQueue, identity: IdentityStore, session: AuthenticatedSession):
        if queue.company_id != session.company_id:
            raise IdentityError("Görev kuyruğu başka firmaya ait.")
        self.queue, self.identity, self.session = queue, identity, session
        with queue._connection() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("""CREATE TABLE IF NOT EXISTS review_workflow_state (
                group_id TEXT PRIMARY KEY REFERENCES review_queue_groups(group_id),
                phase TEXT NOT NULL, due_at TEXT, submitted_by INTEGER,
                decision TEXT, note TEXT NOT NULL DEFAULT '')""")
            c.execute("""CREATE TABLE IF NOT EXISTS review_workflow_audit (
                id INTEGER PRIMARY KEY, company_id INTEGER NOT NULL, group_id TEXT NOT NULL,
                actor_user_id INTEGER NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL)""")
            for verb in ("UPDATE", "DELETE"):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS review_workflow_no_{verb.lower()} BEFORE {verb} ON review_workflow_audit BEGIN SELECT RAISE(ABORT, 'Denetim kaydı değiştirilemez'); END")
            c.execute("CREATE INDEX IF NOT EXISTS review_workflow_audit_scope ON review_workflow_audit(company_id, group_id, id)")

    def _context(self):
        session = self.identity.current_session(self.session)
        if not session.can("history.read"):
            raise IdentityError("Görevleri görüntüleme yetkiniz yok.")
        return session, self.identity.review_regions(session)

    @staticmethod
    def _visible(group, regions):
        return regions is None or all(IdentityStore.normalize_review_region(m.region) in regions for m in group.members)

    def _task(self, c, row):
        group = self.queue._hydrate(c, row)
        state = c.execute("SELECT * FROM review_workflow_state WHERE group_id=?", (group.group_id,)).fetchone()
        phase = state["phase"] if state else {"RESOLVED": "APPROVED"}.get(group.status, group.status)
        return ReviewTask(group, phase, state["due_at"] if state else None,
                          state["submitted_by"] if state else None,
                          state["decision"] if state else row["resolution_code"], state["note"] if state else "")

    def list(self):
        _, regions = self._context()
        with self.queue._connection() as c:
            rows = c.execute("SELECT * FROM review_queue_groups WHERE company_id=? ORDER BY updated_at DESC", (self.session.company_id,)).fetchall()
            tasks = [self._task(c, row) for row in rows]
        return [task for task in tasks if self._visible(task.group, regions)]

    def allowed(self, task, action, session=None):
        session = session or self._context()[0]
        owner = task.group.assigned_user_id == session.user_id
        manager = session.can("operations.review.assign")
        phase = task.phase
        if action == "claim":
            return phase == "OPEN" and session.can("operations.review.assign_self")
        if action == "assign":
            return manager and phase in {"OPEN", "ASSIGNED", "IN_REVIEW", "REJECTED"}
        if action == "start":
            return owner and phase in {"ASSIGNED", "REJECTED"} and session.can("operations.review.work")
        if action == "submit":
            return owner and phase == "IN_REVIEW" and session.can("operations.review.work")
        if action in {"approve", "reject"}:
            return phase == "PENDING_APPROVAL" and session.can("operations.review.approve") and (task.submitted_by != session.user_id or manager)
        if action == "reopen":
            return phase in {"APPROVED", "CANCELLED"} and session.can("operations.review.reopen")
        return False

    def assignees(self, task):
        session, _ = self._context()
        if not session.can("operations.review.assign"):
            return []
        members = self.identity.review_members(session)
        result = []
        for member in members:
            target = AuthenticatedSession(member.user_id, member.username, member.display_name, session.company_id, session.company_code, session.company_name, member.role)
            if target.can("operations.review.work") and self._visible(task.group, self.identity.review_regions(session, member.user_id)):
                result.append(member)
        return result

    def act(self, group_id, action, *, expected_version, target_user_id=None, decision=None, note="", due_at=None):
        session, regions = self._context()
        note = str(note).strip()
        if len(note) > 1000:
            raise ReviewQueueError("Açıklama en fazla 1000 karakter olabilir.")
        if action in {"submit", "approve", "reject", "reopen"} and not note:
            raise ReviewQueueError("Kararın gerekçesini yazın.")
        if action == "submit" and decision not in DECISIONS:
            raise ReviewQueueError("Listeden geçerli bir karar seçin.")
        if due_at:
            try:
                parsed = datetime.fromisoformat(due_at)
                if parsed.tzinfo is None:
                    raise ValueError()
                due_at = parsed.astimezone(timezone.utc).isoformat(timespec="seconds")
            except (ValueError, TypeError):
                raise ReviewQueueError("Hedef tarih saat dilimiyle birlikte geçerli olmalıdır.")
        with self.queue._connection() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM review_queue_groups WHERE group_id=? AND company_id=?", (group_id, session.company_id)).fetchone()
            if row is None:
                raise ReviewQueueError("Görev bulunamadı veya erişiminiz yok.")
            task = self._task(c, row)
            if not self._visible(task.group, regions):
                raise ReviewQueueError("Bu görevin tüm bölgelerine erişiminiz yok.")
            if task.group.version != expected_version:
                raise ReviewQueueError("Görev başka kullanıcı tarafından güncellendi; ekranı yenileyin.")
            if not self.allowed(task, action, session):
                raise ReviewQueueError("Bu işlem için yetkiniz yok veya görev uygun aşamada değil.")
            owner = task.group.assigned_user_id
            submitted = task.submitted_by
            saved_decision = task.decision
            deadline = task.due_at
            if action == "assign":
                if target_user_id not in {m.user_id for m in self.assignees(task)}:
                    raise ReviewQueueError("Hedef kullanıcı aktif, yetkili ve aynı bölge kapsamında olmalıdır.")
                owner = target_user_id
                deadline = due_at
                submitted = saved_decision = None
            elif action == "claim":
                owner = session.user_id
            elif action == "submit":
                submitted, saved_decision = session.user_id, decision
            elif action == "reopen":
                owner = submitted = saved_decision = deadline = None
            phase = {"claim": "ASSIGNED", "assign": "ASSIGNED", "start": "IN_REVIEW", "submit": "PENDING_APPROVAL", "approve": "APPROVED", "reject": "REJECTED", "reopen": "OPEN"}[action]
            status = "RESOLVED" if phase == "APPROVED" else "OPEN" if phase == "OPEN" else "ASSIGNED"
            now = self.queue._now()
            c.execute("UPDATE review_queue_groups SET status=?, assigned_user_id=?, resolution_code=?, updated_at=?, version=version+1 WHERE group_id=? AND company_id=? AND version=?", (status,owner,saved_decision,now,group_id,session.company_id,expected_version))
            c.execute("""INSERT INTO review_workflow_state VALUES (?,?,?,?,?,?)
                       ON CONFLICT(group_id) DO UPDATE SET phase=excluded.phase,due_at=excluded.due_at,submitted_by=excluded.submitted_by,decision=excluded.decision,note=excluded.note""", (group_id,phase,deadline,submitted,saved_decision,note))
            self.queue._add_event(c, group_id, session.user_id, task.group.status, status, expected_version, expected_version+1, saved_decision, now)
            payload = {"before": task.phase, "after": phase, "previous_owner": task.group.assigned_user_id,
                       "owner": owner, "version": expected_version+1, "decision": saved_decision, "note": note,
                       "due_at": deadline, "self_approval": action == "approve" and submitted == session.user_id}
            previous = c.execute("SELECT event_hash FROM review_workflow_audit WHERE company_id=? ORDER BY id DESC LIMIT 1", (session.company_id,)).fetchone()
            previous_hash = previous[0] if previous else ""
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            digest = self._hash(session.company_id, group_id, session.user_id, action, raw, now, previous_hash)
            c.execute("INSERT INTO review_workflow_audit(company_id,group_id,actor_user_id,action,payload,created_at,previous_hash,event_hash) VALUES (?,?,?,?,?,?,?,?)", (session.company_id,group_id,session.user_id,action,raw,now,previous_hash,digest))

    @staticmethod
    def _hash(company, group, actor, action, payload, created, previous):
        return hashlib.sha256(json.dumps([company,group,actor,action,payload,created,previous], ensure_ascii=False).encode()).hexdigest()

    def events(self, group_id):
        visible = {t.group.group_id for t in self.list()}
        if group_id not in visible:
            raise ReviewQueueError("Görev bulunamadı veya erişiminiz yok.")
        with self.queue._connection() as c:
            rows = c.execute("SELECT * FROM review_workflow_audit WHERE group_id=? AND company_id=? ORDER BY id", (group_id,self.session.company_id)).fetchall()
        return [dict(row) for row in rows]

    def audit_valid(self):
        self._context()
        with self.queue._connection() as c:
            rows = c.execute("SELECT * FROM review_workflow_audit WHERE company_id=? ORDER BY id", (self.session.company_id,)).fetchall()
        previous = ""
        for r in rows:
            digest = self._hash(r["company_id"],r["group_id"],r["actor_user_id"],r["action"],r["payload"],r["created_at"],previous)
            if r["previous_hash"] != previous or r["event_hash"] != digest:
                return False
            previous = digest
        return True
