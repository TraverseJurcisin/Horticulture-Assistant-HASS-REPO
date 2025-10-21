from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any

from .events import SyncEvent, decode_ndjson, encode_ndjson

UTC = getattr(datetime, "UTC", timezone.utc)


class EdgeSyncStore:
    """SQLite-backed outbox/inbox store for the Home Assistant add-on."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
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

    # ------------------------------------------------------------------
    def append_outbox(self, event: SyncEvent) -> None:
        payload = event.to_json_line()
        ts = event.ts.replace(tzinfo=UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO outbox_events(event_id, payload, ts, attempts, last_attempt_ts)
                VALUES(?, ?, ?, COALESCE((SELECT attempts FROM outbox_events WHERE event_id = ?), 0),
                       COALESCE((SELECT last_attempt_ts FROM outbox_events WHERE event_id = ?), NULL))
                """,
                (event.event_id, payload, ts, event.event_id, event.event_id),
            )

    def get_outbox_batch(self, limit: int = 100) -> list[SyncEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM outbox_events ORDER BY ts ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [SyncEvent.from_json_line(row["payload"]) for row in rows]

    def mark_outbox_attempt(self, event_ids: Iterable[str]) -> None:
        now = datetime.now(tz=UTC).isoformat()
        with self._connect() as conn:
            for event_id in event_ids:
                conn.execute(
                    """
                    UPDATE outbox_events
                       SET attempts = attempts + 1, last_attempt_ts = ?
                     WHERE event_id = ?
                    """,
                    (now, event_id),
                )

    def mark_outbox_acked(self, event_ids: Iterable[str]) -> None:
        with self._connect() as conn:
            conn.executemany(
                "DELETE FROM outbox_events WHERE event_id = ?",
                ((event_id,) for event_id in event_ids),
            )

    # ------------------------------------------------------------------
    def record_incoming(self, ndjson_payload: str | bytes) -> list[SyncEvent]:
        events = decode_ndjson(ndjson_payload)
        with self._connect() as conn:
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
        return events

    def update_cloud_cache(
        self,
        entity_type: str,
        entity_id: str,
        tenant_id: str,
        payload: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
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

    def fetch_cloud_cache(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM cloud_cache WHERE entity_type = ? AND entity_id = ?
                """,
                (entity_type, entity_id),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def all_cloud_cache(self, entity_type: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload FROM cloud_cache"
        params: tuple[Any, ...] = ()
        if entity_type:
            query += " WHERE entity_type = ?"
            params = (entity_type,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    # ------------------------------------------------------------------
    def get_cursor(self, stream: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cursor FROM sync_cursors WHERE stream = ?",
                (stream,),
            ).fetchone()
        if not row:
            return None
        return row["cursor"]

    def set_cursor(self, stream: str, cursor: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sync_cursors(stream, cursor, updated_at)
                VALUES(?, ?, ?)
                """,
                (stream, cursor, datetime.now(tz=UTC).isoformat()),
            )

    # ------------------------------------------------------------------
    def export_outbox_ndjson(self) -> str:
        events = self.get_outbox_batch(limit=10_000)
        return encode_ndjson(events)

