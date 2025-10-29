from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .events import SyncEvent, VectorClock, decode_ndjson, encode_ndjson

try:
    UTC = datetime.UTC
except AttributeError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017


@dataclass(slots=True)
class CloudCacheRecord:
    """Represents a cached cloud entity scoped to a tenant."""

    entity_type: str
    entity_id: str
    tenant_id: str
    payload: dict[str, Any]
    updated_at: datetime
    org_id: str | None = None


class EdgeSyncStore:
    """SQLite-backed outbox/inbox store for the Home Assistant add-on."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._is_memory = str(self.path) == ":memory:"
        self._shared_conn: sqlite3.Connection | None = None
        self._ensure_schema()

    # ------------------------------------------------------------------
    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if self._is_memory:
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(":memory:")
                self._shared_conn.row_factory = sqlite3.Row
            yield self._shared_conn
        else:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS outbox_events (
                    event_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    last_attempt_ts TEXT
                );

                CREATE TABLE IF NOT EXISTS inbox_events (
                    event_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    ts TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cloud_cache (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    org_id TEXT NOT NULL DEFAULT '',
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, tenant_id, org_id, entity_id)
                );

                CREATE TABLE IF NOT EXISTS sync_cursors (
                    stream TEXT PRIMARY KEY,
                    cursor TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entity_vectors (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    counter INTEGER NOT NULL,
                    PRIMARY KEY (entity_type, entity_id, device_id)
                );
                """
            )
            self._ensure_cloud_cache_schema(conn)
            conn.commit()

    # ------------------------------------------------------------------
    def append_outbox(self, event: SyncEvent) -> None:
        payload = event.to_json_line()
        ts = event.ts.replace(tzinfo=UTC).isoformat()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO outbox_events(event_id, payload, ts, attempts, last_attempt_ts)
                VALUES(?, ?, ?, COALESCE((SELECT attempts FROM outbox_events WHERE event_id = ?), 0),
                       COALESCE((SELECT last_attempt_ts FROM outbox_events WHERE event_id = ?), NULL))
                """,
                (event.event_id, payload, ts, event.event_id, event.event_id),
            )
            self._ensure_cloud_cache_schema(conn)
            conn.commit()

    def _ensure_cloud_cache_schema(self, conn: sqlite3.Connection) -> None:
        columns = {row["name"]: row for row in conn.execute("PRAGMA table_info(cloud_cache)").fetchall()}
        if not columns:
            return
        if "org_id" in columns:
            return
        conn.executescript(
            """
            ALTER TABLE cloud_cache RENAME TO cloud_cache_legacy;
            CREATE TABLE cloud_cache (
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                org_id TEXT NOT NULL DEFAULT '',
                payload TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (entity_type, tenant_id, org_id, entity_id)
            );
            INSERT INTO cloud_cache (entity_type, entity_id, tenant_id, org_id, payload, updated_at)
                SELECT entity_type, entity_id, tenant_id, '', payload, updated_at FROM cloud_cache_legacy;
            DROP TABLE cloud_cache_legacy;
            """
        )

    def get_outbox_batch(self, limit: int = 100) -> list[SyncEvent]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT payload FROM outbox_events ORDER BY ts ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [SyncEvent.from_json_line(row["payload"]) for row in rows]

    def mark_outbox_attempt(self, event_ids: Iterable[str]) -> None:
        now = datetime.now(tz=UTC).isoformat()
        with self._connection() as conn:
            for event_id in event_ids:
                conn.execute(
                    """
                    UPDATE outbox_events
                       SET attempts = attempts + 1, last_attempt_ts = ?
                     WHERE event_id = ?
                    """,
                    (now, event_id),
                )
            conn.commit()

    def mark_outbox_acked(self, event_ids: Iterable[str]) -> None:
        with self._connection() as conn:
            conn.executemany(
                "DELETE FROM outbox_events WHERE event_id = ?",
                ((event_id,) for event_id in event_ids),
            )
            conn.commit()

    # ------------------------------------------------------------------
    def record_incoming(self, ndjson_payload: str | bytes) -> list[SyncEvent]:
        events = decode_ndjson(ndjson_payload)
        with self._connection() as conn:
            for event in events:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO inbox_events(event_id, payload, ts)
                    VALUES(?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.to_json_line(),
                        event.ts.replace(tzinfo=UTC).isoformat(),
                    ),
                )
            conn.commit()
        return events

    def update_cloud_cache(
        self,
        entity_type: str,
        entity_id: str,
        tenant_id: str,
        payload: dict[str, Any],
        *,
        org_id: str | None = None,
    ) -> None:
        org_norm = str(org_id).strip() if org_id is not None else ""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cloud_cache(entity_type, entity_id, tenant_id, org_id, payload, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_type,
                    entity_id,
                    tenant_id,
                    org_norm,
                    json.dumps(payload, separators=(",", ":")),
                    datetime.now(tz=UTC).isoformat(),
                ),
            )
            conn.commit()

    def fetch_cloud_cache_entry(
        self,
        entity_type: str,
        entity_id: str,
        *,
        tenant_id: str | None = None,
        org_id: str | None = None,
    ) -> CloudCacheRecord | None:
        query = (
            "SELECT entity_type, entity_id, tenant_id, org_id, payload, updated_at "
            "FROM cloud_cache WHERE entity_type = ? AND entity_id = ?"
        )
        params: list[Any] = [entity_type, entity_id]
        if tenant_id:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if org_id is not None:
            org_norm = str(org_id).strip()
            query += " AND (org_id = ? OR org_id = '') ORDER BY CASE WHEN org_id = ? THEN 0 ELSE 1 END, updated_at DESC"
            params.extend((org_norm, org_norm))
        else:
            query += " ORDER BY updated_at DESC"
        with self._connection() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        if not row:
            return None
        row_map = dict(row)
        payload_raw = json.loads(row_map["payload"])
        payload = payload_raw if isinstance(payload_raw, dict) else {}
        updated_at = self._parse_timestamp(str(row_map["updated_at"])) or datetime.now(tz=UTC)
        return CloudCacheRecord(
            entity_type=row_map["entity_type"],
            entity_id=row_map["entity_id"],
            tenant_id=row_map["tenant_id"],
            payload=payload,
            updated_at=updated_at,
            org_id=row_map.get("org_id") or None,
        )

    def fetch_cloud_cache(
        self,
        entity_type: str,
        entity_id: str,
        *,
        tenant_id: str | None = None,
        org_id: str | None = None,
    ) -> dict[str, Any] | None:
        record = self.fetch_cloud_cache_entry(
            entity_type,
            entity_id,
            tenant_id=tenant_id,
            org_id=org_id,
        )
        return None if record is None else record.payload

    def list_cloud_cache(
        self,
        entity_type: str | None = None,
        *,
        tenant_id: str | None = None,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return cached cloud entities with metadata."""

        query = "SELECT entity_type, entity_id, tenant_id, org_id, payload, updated_at FROM cloud_cache"
        clauses: list[str] = []
        params: list[Any] = []
        if entity_type:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)
        if org_id is not None:
            clauses.append("org_id = ?")
            params.append(str(org_id).strip())
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC"
        with self._connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "entity_type": row["entity_type"],
                    "entity_id": row["entity_id"],
                    "tenant_id": row["tenant_id"],
                    "org_id": row["org_id"] or None,
                    "payload": json.loads(row["payload"]),
                    "updated_at": row["updated_at"],
                }
            )
        return results

    def all_cloud_cache(
        self,
        entity_type: str | None = None,
        *,
        tenant_id: str | None = None,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return cached payloads without metadata (legacy helper)."""

        return [
            item["payload"]
            for item in self.list_cloud_cache(
                entity_type,
                tenant_id=tenant_id,
                org_id=org_id,
            )
        ]

    # ------------------------------------------------------------------
    def get_cursor(self, stream: str) -> str | None:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT cursor FROM sync_cursors WHERE stream = ?",
                (stream,),
            ).fetchone()
        if not row:
            return None
        return row["cursor"]

    def set_cursor(self, stream: str, cursor: str) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_cursors(stream, cursor, updated_at)
                VALUES(?, ?, ?)
                """,
                (stream, cursor, datetime.now(tz=UTC).isoformat()),
            )
            conn.commit()

    # ------------------------------------------------------------------
    def next_vector(self, entity_type: str, entity_id: str, device_id: str) -> VectorClock:
        """Increment and return the vector clock for ``entity_id``."""

        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT counter
                  FROM entity_vectors
                 WHERE entity_type = ? AND entity_id = ? AND device_id = ?
                """,
                (entity_type, entity_id, device_id),
            ).fetchone()
            counter = int(row["counter"]) + 1 if row else 1
            conn.execute(
                """
                INSERT OR REPLACE INTO entity_vectors(entity_type, entity_id, device_id, counter)
                VALUES(?, ?, ?, ?)
                """,
                (entity_type, entity_id, device_id, counter),
            )
            conn.commit()
        return VectorClock(device=device_id, counter=counter)

    # ------------------------------------------------------------------
    def export_outbox_ndjson(self) -> str:
        events = self.get_outbox_batch(limit=10_000)
        return encode_ndjson(events)

    # ------------------------------------------------------------------
    def outbox_size(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM outbox_events").fetchone()
        if not row:
            return 0
        total = row["total"]
        return int(total) if total is not None else 0

    def count_cloud_cache(self) -> int:
        with self._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM cloud_cache").fetchone()
        if not row:
            return 0
        total = row["total"]
        return int(total) if total is not None else 0

    def newest_cloud_cache_update(self) -> datetime | None:
        return self._fetch_cloud_cache_timestamp("MAX")

    def oldest_cloud_cache_update(self) -> datetime | None:
        return self._fetch_cloud_cache_timestamp("MIN")

    def cloud_cache_age(self, *, now: datetime | None = None) -> float | None:
        latest = self.newest_cloud_cache_update()
        if latest is None:
            return None
        now = now or datetime.now(tz=UTC)
        delta = now - latest.astimezone(UTC)
        return max(delta.total_seconds() / 86400, 0.0)

    def cloud_cache_oldest_age(self, *, now: datetime | None = None) -> float | None:
        oldest = self.oldest_cloud_cache_update()
        if oldest is None:
            return None
        now = now or datetime.now(tz=UTC)
        delta = now - oldest.astimezone(UTC)
        return max(delta.total_seconds() / 86400, 0.0)

    # ------------------------------------------------------------------
    def _fetch_cloud_cache_timestamp(self, aggregate: str) -> datetime | None:
        query = f"SELECT {aggregate}(updated_at) AS ts FROM cloud_cache"
        with self._connection() as conn:
            row = conn.execute(query).fetchone()
        if not row:
            return None
        raw = row["ts"]
        if raw is None:
            return None
        return self._parse_timestamp(str(raw))

    def _parse_timestamp(self, value: str) -> datetime | None:
        try:
            ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)
