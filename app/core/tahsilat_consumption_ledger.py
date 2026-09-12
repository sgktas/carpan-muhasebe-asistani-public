from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import sqlite3
from typing import Iterable

from app.models.records import TahsilatRecord


def _cents(value: float | Decimal) -> int:
    return int(
        (Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)
    )


def _amount(cents: int) -> float:
    return float(Decimal(int(cents)) / 100)


@dataclass(frozen=True)
class TahsilatBalance:
    source_hash: str
    source_sheet: str
    source_row: int
    original_amount: float
    consumed_amount: float
    remaining_amount: float


class TahsilatConsumptionError(RuntimeError):
    """A source collection row cannot be safely consumed again."""


class TahsilatConsumptionLedger:
    """Firma kapsamlı, satır kimlikli tahsilat kullanım defteri.

    Defter yalnız kaynak dosya özeti, sayfa/satır ve kuruş tutarını saklar.
    Müşteri adı, banka açıklaması veya Excel yolu tutulmaz. Simülasyon bu
    servisi yalnız okunur biçimde kullanır; yazma gerçek yayın akışının son
    kalıcı etkilerindendir.
    """

    def __init__(self, database_path: str | Path, *, company_id: int | None = None):
        self.database_path = Path(database_path)
        self.company_id = company_id
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tahsilat_consumptions (
                    company_id INTEGER,
                    source_hash TEXT NOT NULL,
                    source_sheet TEXT NOT NULL,
                    source_row INTEGER NOT NULL,
                    operation_id INTEGER,
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_tahsilat_consumption_source
                ON tahsilat_consumptions(company_id, source_hash, source_sheet, source_row)
                """
            )

    def balances(self, rows: Iterable[TahsilatRecord]) -> tuple[TahsilatBalance, ...]:
        source_rows = [row for row in rows if self._has_source_identity(row)]
        if not source_rows:
            return ()
        consumed = self._consumed_cents(source_rows)
        return tuple(
            TahsilatBalance(
                source_hash=row.source_hash,
                source_sheet=row.source_sheet,
                source_row=int(row.source_row),
                original_amount=_amount(_cents(row.source_amount if row.source_amount is not None else row.tutar)),
                consumed_amount=_amount(consumed.get(self._key(row), 0)),
                remaining_amount=_amount(max(0, _cents(row.source_amount if row.source_amount is not None else row.tutar) - consumed.get(self._key(row), 0))),
            )
            for row in source_rows
        )

    def available_rows(
        self,
        rows: Iterable[TahsilatRecord],
        *,
        reusable_operation_ids: Iterable[int] = (),
    ) -> list[TahsilatRecord]:
        """Return only the still-available value of source-identifiable rows.

        Legacy/manual rows without source identity remain usable because the
        application cannot truthfully claim they are a specific report line.
        """
        rows = list(rows)
        consumed = self._consumed_cents(
            (row for row in rows if self._has_source_identity(row)),
            excluding_operation_ids=reusable_operation_ids,
        )
        available: list[TahsilatRecord] = []
        for row in rows:
            if not self._has_source_identity(row):
                available.append(row)
                continue
            original = row.source_amount if row.source_amount is not None else row.tutar
            remaining = _cents(original) - consumed.get(self._key(row), 0)
            if remaining > 0:
                available.append(replace(row, tutar=_amount(remaining)))
        return available

    def consume(self, rows: Iterable[TahsilatRecord], *, operation_id: int | None) -> int:
        return self.replace_for_retry(rows, operation_id=operation_id)

    def replace_for_retry(
        self,
        rows: Iterable[TahsilatRecord],
        *,
        operation_id: int | None,
        reusable_operation_ids: Iterable[int] = (),
    ) -> int:
        """Atomically move exact-source retry allocations to the new run."""
        requested = self._requested(rows)
        allocations = {key: allocated for key, (_original, allocated) in requested.items()}
        if not allocations:
            return 0

        reusable_ids = tuple(sorted({int(value) for value in reusable_operation_ids}))

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for key, (original, amount_cents) in requested.items():
                    already = self._consumed_cents_for_key(
                        connection, key, excluding_operation_ids=reusable_ids,
                    )
                    if amount_cents <= 0:
                        raise TahsilatConsumptionError("Tahsilat kullanım tutarı pozitif olmalıdır.")
                    if already + amount_cents > original:
                        raise TahsilatConsumptionError(
                            "Tahsilat satırının kullanılabilir bakiyesi yetersiz; "
                            "raporu yenileyin ve eşleştirmeyi tekrar kontrol edin."
                        )
                if reusable_ids:
                    placeholders = ",".join("?" for _ in reusable_ids)
                    connection.execute(
                        f"DELETE FROM tahsilat_consumptions "
                        f"WHERE company_id IS ? AND operation_id IN ({placeholders})",
                        (self.company_id, *reusable_ids),
                    )
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                for key, amount_cents in allocations.items():
                    connection.execute(
                        """INSERT INTO tahsilat_consumptions
                           (company_id, source_hash, source_sheet, source_row, operation_id, amount_cents, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (self.company_id, key[0], key[1], key[2], operation_id, amount_cents, now),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return len(allocations)

    def assert_can_consume(
        self,
        rows: Iterable[TahsilatRecord],
        *,
        reusable_operation_ids: Iterable[int] = (),
    ) -> None:
        """Validate every allocation against the immutable source row amount."""
        requested = self._requested(rows)
        if not requested:
            return
        with self._connection() as connection:
            for key, (original, allocated) in requested.items():
                used = self._consumed_cents_for_key(
                    connection, key,
                    excluding_operation_ids=reusable_operation_ids,
                )
                if used + allocated > original:
                    raise TahsilatConsumptionError(
                        "Tahsilat satırının kullanılabilir bakiyesi yetersiz; "
                        "raporu yenileyin ve eşleştirmeyi tekrar kontrol edin."
                    )

    def _requested(self, rows: Iterable[TahsilatRecord]) -> dict[tuple[str, str, int], tuple[int, int]]:
        requested: dict[tuple[str, str, int], tuple[int, int]] = {}
        for row in rows:
            if not self._has_source_identity(row):
                continue
            key = self._key(row)
            source_amount = row.source_amount if row.source_amount is not None else row.tutar
            original, allocated = requested.get(key, (_cents(source_amount), 0))
            requested[key] = (original, allocated + _cents(row.tutar))
        return requested

    def _consumed_cents(
        self,
        rows: Iterable[TahsilatRecord],
        *,
        excluding_operation_ids: Iterable[int] = (),
    ) -> dict[tuple[str, str, int], int]:
        keys = {self._key(row) for row in rows if self._has_source_identity(row)}
        if not keys:
            return {}
        with self._connection() as connection:
            return {
                key: self._consumed_cents_for_key(
                    connection, key,
                    excluding_operation_ids=excluding_operation_ids,
                )
                for key in keys
            }

    def _consumed_cents_for_key(
        self,
        connection: sqlite3.Connection,
        key: tuple[str, str, int],
        *,
        excluding_operation_ids: Iterable[int] = (),
    ) -> int:
        excluded = tuple(sorted({int(value) for value in excluding_operation_ids}))
        exclusion_sql = ""
        params: list[object] = [self.company_id, key[0], key[1], key[2]]
        if excluded:
            placeholders = ",".join("?" for _ in excluded)
            exclusion_sql = f" AND (operation_id IS NULL OR operation_id NOT IN ({placeholders}))"
            params.extend(excluded)
        row = connection.execute(
            f"""SELECT COALESCE(SUM(amount_cents), 0) AS total
               FROM tahsilat_consumptions
               WHERE company_id IS ? AND source_hash = ? AND source_sheet = ? AND source_row = ?
               {exclusion_sql}""",
            params,
        ).fetchone()
        return int(row["total"] or 0)

    @staticmethod
    def _has_source_identity(row: TahsilatRecord) -> bool:
        return bool(row.source_hash and row.source_sheet and int(row.source_row) > 0)

    @staticmethod
    def _key(row: TahsilatRecord) -> tuple[str, str, int]:
        return (str(row.source_hash), str(row.source_sheet), int(row.source_row))
