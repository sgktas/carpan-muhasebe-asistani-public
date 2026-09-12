"""Durable boundary between a published MANİM output folder and local state.

This is deliberately a *stop and recover* journal.  A filesystem folder and
SQLite cannot share one atomic transaction; when the process stops between the
two, replaying silently could duplicate an ERP transfer.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


class PublicationRecoveryRequired(RuntimeError):
    """A previous output was published but its local commit was interrupted."""


@dataclass(frozen=True)
class PublicationEntry:
    publication_id: str
    company_id: int | None
    operation_id: int | None
    status: str
    source_hashes: tuple[str, ...]
    output_dir: str
    output_files: tuple[str, ...]
    published_at: str
    committed_at: str | None


class PublicationJournal:
    """Records only source hashes and output paths, never bank/customer data."""

    def __init__(self, database_path: str | Path, *, company_id: int | None = None):
        self.database_path = Path(database_path)
        self.company_id = company_id
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS manim_publications (
                    publication_id TEXT PRIMARY KEY,
                    company_id INTEGER,
                    operation_id INTEGER,
                    status TEXT NOT NULL CHECK(status IN ('PUBLISHED', 'COMMITTED', 'RECOVERY_CONFIRMED')),
                    source_hashes_json TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    output_files_json TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    committed_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_manim_publication_scope ON manim_publications(company_id, status, published_at DESC)"
            )

    def assert_reprocessable(self, source_hashes: list[str]) -> None:
        wanted = {str(value) for value in source_hashes if value}
        if not wanted:
            return
        for entry in self.list(status="PUBLISHED"):
            if wanted.intersection(entry.source_hashes):
                raise PublicationRecoveryRequired(
                    "Bu kaynaklar için tamamlanmamış bir çıktı yayını var: "
                    f"{entry.output_dir}. Aynı aktarımı tekrar başlatmadan önce "
                    "Operasyon Merkezi'nden kurtarma kaydını inceleyin."
                )

    def publish(self, *, operation_id: int | None, source_hashes: list[str], output_dir: str | Path,
                output_files: list[str | Path]) -> str:
        normalized = tuple(sorted({str(value) for value in source_hashes if value}))
        if not normalized:
            raise ValueError("Yayın günlüğü için en az bir kaynak özeti zorunludur.")
        publication_id = uuid4().hex
        now = self._now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO manim_publications
                   (publication_id, company_id, operation_id, status, source_hashes_json,
                    output_dir, output_files_json, published_at)
                   VALUES (?, ?, ?, 'PUBLISHED', ?, ?, ?, ?)""",
                (publication_id, self.company_id, operation_id, json.dumps(normalized),
                 str(output_dir), json.dumps([str(path) for path in output_files]), now),
            )
        return publication_id

    def commit(self, publication_id: str) -> None:
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE manim_publications SET status = 'COMMITTED', committed_at = ?
                   WHERE publication_id = ? AND company_id IS ? AND status = 'PUBLISHED'""",
                (self._now(), str(publication_id), self.company_id),
            )
            if cursor.rowcount != 1:
                raise PublicationRecoveryRequired("Yayın günlüğü güncel değil; kurtarma kontrolü gerekli.")

    def approve_retry(self, publication_id: str) -> None:
        """Explicitly permit a new run after the user verified the old output.

        The output folder is not deleted and no ERP claim is made.  This is a
        visible, auditable escape hatch for the case where the user confirms
        the published folder was never imported externally.
        """
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE manim_publications SET status = 'RECOVERY_CONFIRMED', committed_at = ?
                   WHERE publication_id = ? AND company_id IS ? AND status = 'PUBLISHED'""",
                (self._now(), str(publication_id), self.company_id),
            )
            if cursor.rowcount != 1:
                raise PublicationRecoveryRequired("Kurtarma kaydı güncel değil; ekranı yenileyin.")

    def committed_operation_ids_for_exact_sources(
        self,
        source_hashes: list[str] | set[str],
    ) -> tuple[int, ...]:
        """Return prior completed runs for exactly the same MANİM source set.

        This is intentionally stricter than an intersection check. A retry may
        reuse receipt allocations only when the user selected the same complete
        set of source reports; otherwise an unrelated region could regain a
        receipt that belongs to another transfer.
        """
        wanted = tuple(sorted({str(value) for value in source_hashes if value}))
        if not wanted:
            return ()
        operation_ids: list[int] = []
        for entry in self.list(status="COMMITTED"):
            if entry.operation_id is not None and entry.source_hashes == wanted:
                operation_ids.append(int(entry.operation_id))
        return tuple(operation_ids)

    def list(self, *, status: str | None = None, limit: int = 100) -> tuple[PublicationEntry, ...]:
        clauses = ["company_id IS ?"]
        params: list[object] = [self.company_id]
        if status:
            clauses.append("status = ?")
            params.append(str(status).upper())
        params.append(max(1, int(limit)))
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM manim_publications WHERE {' AND '.join(clauses)} ORDER BY published_at DESC LIMIT ?",
                params,
            ).fetchall()
        return tuple(
            PublicationEntry(
                publication_id=str(row["publication_id"]), company_id=row["company_id"],
                operation_id=row["operation_id"], status=str(row["status"]),
                source_hashes=tuple(json.loads(row["source_hashes_json"])), output_dir=str(row["output_dir"]),
                output_files=tuple(json.loads(row["output_files_json"])), published_at=str(row["published_at"]),
                committed_at=row["committed_at"],
            ) for row in rows
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
