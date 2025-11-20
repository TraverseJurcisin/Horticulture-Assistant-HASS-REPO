from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from ..utils.aiohttp import ClientError, ClientSession
from .conflict import ConflictPolicy, ConflictResolver
from .edge_store import EdgeSyncStore
from .events import SyncEvent, encode_ndjson

LOGGER = logging.getLogger(__name__)


class EdgeSyncWorker:
    """Bidirectional sync worker for the Home Assistant edge add-on."""

    def __init__(
        self,
        store: EdgeSyncStore,
        session: ClientSession,
        base_url: str,
        device_token: str,
        tenant_id: str,
        *,
        organization_id: str | None = None,
        conflict_resolver: ConflictResolver | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.store = store
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.device_token = device_token
        self.tenant_id = tenant_id
        self.organization_id = organization_id.strip() if isinstance(organization_id, str) else None
        self.conflicts = conflict_resolver or ConflictResolver(
            field_policies={
                "batch_tags": ConflictPolicy.OR_SET,
                "header.notes": ConflictPolicy.MV_REGISTER,
            }
        )
        self.logger = logger or LOGGER
        self.last_push_error: str | None = None
        self.last_pull_error: str | None = None
        self.last_success_at: datetime | None = None

    # ------------------------------------------------------------------
    async def push_once(self, limit: int = 100) -> int:
        events = self.store.get_outbox_batch(limit)
        if not events:
            return 0
        ndjson_payload = encode_ndjson(events)
        headers = {
            "Authorization": f"Bearer {self.device_token}",
            "Content-Type": "application/x-ndjson",
            "X-Tenant-ID": self.tenant_id,
        }
        if self.organization_id:
            headers["X-Org-ID"] = self.organization_id
        try:
            async with self.session.post(
                f"{self.base_url}/sync/up",
                data=ndjson_payload,
                headers=headers,
                timeout=30,
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise ClientError(f"sync/up failed: {resp.status} {text}")
                acked = self._parse_ack_response(text)
        except ClientError as err:
            self.logger.warning("Sync push failed: %s", err)
            self.store.mark_outbox_attempt(event.event_id for event in events)
            self.last_push_error = str(err)
            return 0

        self.store.mark_outbox_acked(acked)
        self.last_push_error = None
        self.last_success_at = datetime.now(tz=UTC)
        return len(acked)

    async def pull_once(self) -> int:
        cursor = self.store.get_cursor("cloud")
        headers = {
            "Authorization": f"Bearer {self.device_token}",
            "Accept": "application/x-ndjson, application/json",
            "X-Tenant-ID": self.tenant_id,
        }
        if self.organization_id:
            headers["X-Org-ID"] = self.organization_id
        params = {}
        if cursor:
            params["cursor"] = cursor
        try:
            async with self.session.get(
                f"{self.base_url}/sync/down",
                params=params,
                headers=headers,
                timeout=30,
            ) as resp:
                content_type = resp.headers.get("Content-Type", "")
                body = await resp.read()
                if resp.status == 204 or not body.strip():
                    return 0
                if resp.status >= 400:
                    raise ClientError(f"sync/down failed: {resp.status} {body.decode()}")
                ndjson_payload, next_cursor = self._parse_down_response(body, content_type, resp.headers)
        except ClientError as err:
            self.logger.warning("Sync pull failed: %s", err)
            self.last_pull_error = str(err)
            return 0

        events = self.store.record_incoming(ndjson_payload)
        for event in events:
            if event.tenant_id != self.tenant_id:
                continue
            self._apply_to_cache(event)
        if next_cursor:
            self.store.set_cursor("cloud", next_cursor)
        self.last_pull_error = None
        self.last_success_at = datetime.now(tz=UTC)
        return len(events)

    async def run_forever(self, *, interval_seconds: int = 60) -> None:
        while True:
            try:
                await self.push_once()
                await self.pull_once()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # pragma: no cover - defensive log
                self.logger.exception("Unexpected sync error: %s", err)
                self.last_pull_error = str(err)
            await asyncio.sleep(interval_seconds)

    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_push_error": self.last_push_error,
            "last_pull_error": self.last_pull_error,
            "cursor": self.store.get_cursor("cloud"),
            "organization_id": self.organization_id,
        }

    def _parse_ack_response(self, text: str) -> list[str]:
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError:
            return []
        acked = payload.get("acked")
        if isinstance(acked, list):
            return [str(item) for item in acked]
        return []

    def _parse_down_response(
        self, body: bytes, content_type: str, headers: Mapping[str, str]
    ) -> tuple[str, str | None]:
        if content_type.startswith("application/json"):
            payload = json.loads(body.decode())
            events = payload.get("events") if isinstance(payload, Mapping) else payload
            cursor = payload.get("cursor") if isinstance(payload, Mapping) else None
            return self._normalise_events(events), cursor
        cursor = headers.get("X-Sync-Cursor")
        return body.decode(), cursor

    def _normalise_events(self, events: Any) -> str:
        if isinstance(events, bytes):
            return events.decode("utf-8", "ignore")
        if isinstance(events, str):
            return events
        if isinstance(events, Sequence) and not isinstance(events, str | bytes | bytearray):
            lines: list[str] = []
            for item in events:
                text = self._normalise_events(item)
                text = text.strip()
                if text:
                    lines.append(text)
            return "\n".join(lines)
        if isinstance(events, Mapping):
            try:
                return json.dumps(events, separators=(",", ":"), sort_keys=True)
            except (TypeError, ValueError):
                return ""
        if events is None:
            return ""
        try:
            return json.dumps(events, separators=(",", ":"))
        except (TypeError, ValueError):
            return ""

    def _apply_to_cache(self, event: SyncEvent) -> None:
        record = self.store.fetch_cloud_cache_entry(
            event.entity_type,
            event.entity_id,
            tenant_id=event.tenant_id,
            org_id=event.org_id or self.organization_id,
        )
        current = record.payload if record else {}
        merged = self.conflicts.apply(current, event)
        merged.pop("__meta__", None)
        self.store.update_cloud_cache(
            event.entity_type,
            event.entity_id,
            event.tenant_id,
            merged,
            org_id=event.org_id or self.organization_id,
        )
