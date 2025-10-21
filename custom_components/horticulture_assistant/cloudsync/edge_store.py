from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .events import SyncEvent, decode_ndjson, encode_ndjson

UTC = datetime.UTC


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
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                );

                CREATE TABLE IF NOT EXISTS sync_cursors (
                    stream TEXT PRIMARY KEY,
                    cursor TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
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
            conn.commit()

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
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cloud_cache(entity_type, entity_id, tenant_id, payload, updated_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    entity_type,
                    entity_id,
                    tenant_id,
                    json.dumps(payload, separators=(",", ":")),
                    datetime.now(tz=UTC).isoformat(),
                ),
            )
            conn.commit()

    def fetch_cloud_cache(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT payload FROM cloud_cache WHERE entity_type = ? AND entity_id = ?
                """,
                (entity_type, entity_id),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def list_cloud_cache(self, entity_type: str | None = None) -> list[dict[str, Any]]:
        """Return cached cloud entities with metadata."""

        query = "SELECT entity_type, entity_id, tenant_id, payload, updated_at FROM cloud_cache"
        params: tuple[Any, ...] = ()
        if entity_type:
            query += " WHERE entity_type = ?"
            params = (entity_type,)
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "entity_type": row["entity_type"],
                    "entity_id": row["entity_id"],
                    "tenant_id": row["tenant_id"],
                    "payload": json.loads(row["payload"]),
                    "updated_at": row["updated_at"],
                }
            )
        return results

    def all_cloud_cache(self, entity_type: str | None = None) -> list[dict[str, Any]]:
        """Return cached payloads without metadata (legacy helper)."""

        return [item["payload"] for item in self.list_cloud_cache(entity_type)]

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
    def export_outbox_ndjson(self) -> str:
        events = self.get_outbox_batch(limit=10_000)
        return encode_ndjson(events)
