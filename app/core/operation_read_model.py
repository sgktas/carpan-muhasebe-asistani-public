"""Read-only projection over the existing local operation stores.

The stores remain authoritative and keep their independent transaction
boundaries.  This module only preserves their observable facts and derives
small, explainable consistency signals for future UI use.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.operation_history import OperationHistory, OperationRecord
    from app.core.processed_files_log import ProcessedFilesLog
    from app.core.publication_journal import PublicationEntry, PublicationJournal
    from app.core.review_queue import ReviewGroup, ReviewQueue
    from app.core.review_workflow import ReviewWorkflow


CONSISTENT = "CONSISTENT"
ATTENTION = "ATTENTION"
RECOVERY_REQUIRED = "RECOVERY_REQUIRED"

PUBLICATION_PENDING_COMMIT = "publication_pending_commit"
HISTORY_PUBLICATION_MISMATCH = "history_publication_mismatch"
REVIEW_PENDING = "review_pending"
OUTPUT_MISSING = "output_missing"
PROCESSED_SOURCE_MISSING = "processed_source_missing"

_ALL_RECORDS = 2_147_483_647
_FINAL_HISTORY_STATUSES = frozenset({"SUCCESS", "PARTIAL"})
_CLOSED_REVIEW_PHASES = frozenset({"APPROVED", "CANCELLED"})
_CLOSED_REVIEW_STATUSES = frozenset({"RESOLVED", "CANCELLED"})


@dataclass(frozen=True)
class PublicationObservation:
    publication_id: str
    status: str
    source_hashes: tuple[str, ...]
    output_dir: str
    output_files: tuple[str, ...]
    published_at: str
    committed_at: str | None


@dataclass(frozen=True)
class ReviewObservation:
    group_id: str
    status: str
    phase: str | None
    member_count: int
    updated_at: str

    @property
    def pending(self) -> bool:
        if self.phase is not None:
            return self.phase not in _CLOSED_REVIEW_PHASES
        return self.status not in _CLOSED_REVIEW_STATUSES


@dataclass(frozen=True)
class UnifiedOperationView:
    operation_id: int
    company_id: int | None
    module_id: str
    history_status: str
    history_started_at: str
    history_finished_at: str | None
    history_output_files: tuple[str, ...]
    publications: tuple[PublicationObservation, ...]
    reviews: tuple[ReviewObservation, ...]
    processed_source_state: str
    output_presence_state: str
    consistency_status: str
    attention_reasons: tuple[str, ...]

    @property
    def publication_status(self) -> str | None:
        return self.publications[0].status if self.publications else None

    @property
    def publication_id(self) -> str | None:
        return self.publications[0].publication_id if self.publications else None

    @property
    def publication_output_files(self) -> tuple[str, ...]:
        return self.publications[0].output_files if self.publications else ()

    @property
    def open_review_group_count(self) -> int:
        return sum(review.pending for review in self.reviews)

    @property
    def pending_review_count(self) -> int:
        return sum(
            review.member_count for review in self.reviews if review.pending
        )


class OperationReadModel:
    """Build immutable operation views without mutating authoritative stores."""

    def __init__(
        self,
        history: OperationHistory,
        *,
        publication_journal: PublicationJournal | None = None,
        review_queue: ReviewQueue | None = None,
        review_workflow: ReviewWorkflow | None = None,
        processed_files: ProcessedFilesLog | None = None,
    ):
        self.history = history
        self.publication_journal = publication_journal
        self.review_queue = review_queue
        self.review_workflow = review_workflow
        self.processed_files = processed_files
        self.company_id = history.company_id
        self._validate_scope(publication_journal, "publication journal")
        self._validate_scope(review_queue, "review queue")
        if review_workflow is not None:
            workflow_company = review_workflow.session.company_id
            if workflow_company != self.company_id:
                raise ValueError("Review workflow belongs to a different company scope.")

    def get_operation_view(
        self,
        operation_id: int | None,
        *,
        company_id: int | None = None,
    ) -> UnifiedOperationView | None:
        """Return one company-scoped projection, or ``None`` when it cannot join.

        A missing operation identity is intentionally not replaced with a
        synthetic ID.  Journal/review/consumption rows whose operation ID is
        null therefore cannot form an operation-level view.
        """
        if operation_id is None:
            return None
        if company_id is not None and company_id != self.company_id:
            return None
        operation = next(
            (
                record for record in self.history.recent(None)
                if record.id == int(operation_id)
            ),
            None,
        )
        if operation is None:
            return None

        publications = self._publications(operation.id)
        reviews = self._reviews(operation.id)
        processed_state = self._processed_source_state(publications)
        output_state = self._output_presence_state(operation, publications)
        reasons = self._attention_reasons(
            operation, publications, reviews, processed_state, output_state,
        )
        status = (
            RECOVERY_REQUIRED
            if PUBLICATION_PENDING_COMMIT in reasons
            else ATTENTION
            if reasons
            else CONSISTENT
        )
        return UnifiedOperationView(
            operation_id=operation.id,
            company_id=operation.company_id,
            module_id=operation.module_id,
            history_status=operation.status,
            history_started_at=operation.started_at,
            history_finished_at=operation.completed_at,
            history_output_files=tuple(operation.output_files),
            publications=publications,
            reviews=reviews,
            processed_source_state=processed_state,
            output_presence_state=output_state,
            consistency_status=status,
            attention_reasons=reasons,
        )

    def _publications(self, operation_id: int) -> tuple[PublicationObservation, ...]:
        if self.publication_journal is None:
            return ()
        return tuple(
            self._publication_observation(entry)
            for entry in self.publication_journal.list(
                status=None, limit=_ALL_RECORDS,
            )
            if entry.operation_id == operation_id
        )

    def _reviews(self, operation_id: int) -> tuple[ReviewObservation, ...]:
        if self.review_queue is None:
            return ()
        groups = tuple(
            group
            for group in self.review_queue.list(status=None, limit=_ALL_RECORDS)
            if group.operation_id == operation_id
        )
        phases = {}
        if self.review_workflow is not None:
            phases = {
                task.group.group_id: task.phase
                for task in self.review_workflow.list()
            }
        return tuple(
            self._review_observation(group, phases.get(group.group_id))
            for group in groups
        )

    def _processed_source_state(
        self, publications: tuple[PublicationObservation, ...],
    ) -> str:
        source_hashes = {
            source_hash
            for publication in publications
            for source_hash in publication.source_hashes
        }
        if not source_hashes:
            return "NO_SOURCES"
        if self.processed_files is None:
            return "UNKNOWN"
        processed_count = sum(
            self.processed_files.is_processed(source_hash) is not None
            for source_hash in source_hashes
        )
        if processed_count == len(source_hashes):
            return "ALL_PROCESSED"
        if processed_count:
            return "PARTIALLY_PROCESSED"
        return "NONE_PROCESSED"

    @staticmethod
    def _output_presence_state(
        operation: OperationRecord,
        publications: tuple[PublicationObservation, ...],
    ) -> str:
        paths = tuple(dict.fromkeys(
            [*operation.output_files]
            + [
                path
                for publication in publications
                for path in publication.output_files
            ]
        ))
        if not paths:
            return "NONE_RECORDED"
        existing = sum(Path(path).is_file() for path in paths)
        if existing == len(paths):
            return "PRESENT"
        if existing:
            return "PARTIALLY_MISSING"
        return "MISSING"

    @staticmethod
    def _attention_reasons(
        operation: OperationRecord,
        publications: tuple[PublicationObservation, ...],
        reviews: tuple[ReviewObservation, ...],
        processed_state: str,
        output_state: str,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if any(item.status == "PUBLISHED" for item in publications):
            reasons.append(PUBLICATION_PENDING_COMMIT)
        if (
            any(item.status == "COMMITTED" for item in publications)
            and operation.status not in _FINAL_HISTORY_STATUSES
        ):
            reasons.append(HISTORY_PUBLICATION_MISMATCH)
        if any(review.pending for review in reviews):
            reasons.append(REVIEW_PENDING)
        if output_state in {"MISSING", "PARTIALLY_MISSING"}:
            reasons.append(OUTPUT_MISSING)
        if (
            any(item.status == "COMMITTED" for item in publications)
            and processed_state in {"NONE_PROCESSED", "PARTIALLY_PROCESSED"}
        ):
            reasons.append(PROCESSED_SOURCE_MISSING)
        return tuple(reasons)

    def _validate_scope(self, store, label: str) -> None:
        if store is not None and store.company_id != self.company_id:
            raise ValueError(f"{label} belongs to a different company scope.")

    @staticmethod
    def _publication_observation(entry: PublicationEntry) -> PublicationObservation:
        return PublicationObservation(
            publication_id=entry.publication_id,
            status=entry.status,
            source_hashes=entry.source_hashes,
            output_dir=entry.output_dir,
            output_files=entry.output_files,
            published_at=entry.published_at,
            committed_at=entry.committed_at,
        )

    @staticmethod
    def _review_observation(
        group: ReviewGroup, phase: str | None,
    ) -> ReviewObservation:
        return ReviewObservation(
            group_id=group.group_id,
            status=group.status,
            phase=phase,
            member_count=len(group.members),
            updated_at=group.updated_at,
        )

