from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from aiohttp import web

from custom_components.horticulture_assistant.cloudsync import (
    ConflictResolver,
    EdgeResolverService,
    EdgeSyncStore,
    SyncEvent,
    VectorClock,
    decode_ndjson,
    encode_ndjson,
)

UTC = getattr(datetime, "UTC", timezone.utc)


@dataclass
class CloudEntity:
    entity_type: str
    entity_id: str
    tenant_id: str
    payload: dict[str, Any]
    updated_at: datetime


class CloudState:
    """In-memory reference implementation for the cloud service."""

    def __init__(self) -> None:
        self.events: list[SyncEvent] = []
        self.entities: dict[tuple[str, str], CloudEntity] = {}
        self.conflicts = ConflictResolver()
        self.cursor = 0

    def ingest(self, ndjson_payload: str) -> list[str]:
        events = decode_ndjson(ndjson_payload)
        acked: list[str] = []
        for event in events:
            self.cursor += 1
            event.metadata.setdefault("cursor", self.cursor)
            acked.append(event.event_id)
            self.events.append(event)
            key = (event.entity_type, event.entity_id)
            current = self.entities.get(key)
            payload = current.payload if current else {}
            merged = self.conflicts.apply(payload, event)
            merged.pop("__meta__", None)
            self.entities[key] = CloudEntity(
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                tenant_id=event.tenant_id,
                payload=merged,
                updated_at=event.ts,
            )
        return acked

    def stream(self, cursor: int | None) -> tuple[str, int | None]:
        if cursor is None:
            start = 0
        else:
            start = cursor
        pending = [event for event in self.events if event.metadata.get("cursor", 0) > start]
        if not pending:
            return "", cursor
        ndjson_payload = encode_ndjson(pending)
        next_cursor = pending[-1].metadata.get("cursor")
        return ndjson_payload, int(next_cursor) if next_cursor is not None else cursor

    def resolve(self, profile_id: str, field: str) -> Mapping[str, Any]:
        profile_payload = self.entities.get(("profile", profile_id))
        if not profile_payload:
            raise web.HTTPNotFound(text=f"Profile {profile_id} not found")
        store = EdgeSyncStore(":memory:")
        store.update_cloud_cache("profile", profile_id, profile_payload.tenant_id, profile_payload.payload)
        parents = profile_payload.payload.get("parents") or []
        for parent_id in parents:
            parent_payload = self.entities.get(("profile", str(parent_id)))
            if parent_payload:
                store.update_cloud_cache("profile", str(parent_id), parent_payload.tenant_id, parent_payload.payload)
        species_id = parents[-1] if parents else profile_id
        stats = self.entities.get(("computed", str(species_id)))
        if stats:
            store.update_cloud_cache("computed", str(species_id), stats.tenant_id, stats.payload)
        resolver = EdgeResolverService(store)
        result = resolver.resolve_field(profile_id, field)
        return {
            "value": result.value,
            "provenance": result.provenance,
            "overlay": result.overlay,
            "overlay_provenance": result.overlay_provenance,
            "staleness_days": result.staleness_days,
        }


async def handle_sync_up(request: web.Request) -> web.Response:
    tenant = request.headers.get("X-Tenant-ID")
    if not tenant:
        raise web.HTTPUnauthorized(text="missing tenant header")
    payload = await request.text()
    acked = request.app["state"].ingest(payload)
    return web.json_response({"acked": acked})


async def handle_sync_down(request: web.Request) -> web.Response:
    state: CloudState = request.app["state"]
    cursor_raw = request.query.get("cursor")
    cursor = int(cursor_raw) if cursor_raw else None
    ndjson_payload, next_cursor = state.stream(cursor)
    if not ndjson_payload:
        raise web.HTTPNoContent()
    headers = {}
    if next_cursor is not None:
        headers["X-Sync-Cursor"] = str(next_cursor)
    return web.Response(text=ndjson_payload, content_type="application/x-ndjson", headers=headers)


async def handle_resolve(request: web.Request) -> web.Response:
    profile_id = request.query.get("profile")
    field = request.query.get("field")
    if not profile_id or not field:
        raise web.HTTPBadRequest(text="profile and field query params required")
    result = request.app["state"].resolve(profile_id, field)
    return web.json_response(result)


async def handle_profiles(request: web.Request) -> web.Response:
    state: CloudState = request.app["state"]
    if request.method == "GET":
        items = [asdict(entity) for entity in state.entities.values() if entity.entity_type == "profile"]
        for item in items:
            item["updated_at"] = item["updated_at"].isoformat()
        return web.json_response({"profiles": items})
    data = await request.json()
    profile_id = data.get("profile_id")
    if not profile_id:
        raise web.HTTPBadRequest(text="profile_id required")
    event = SyncEvent(
        event_id=data.get("event_id", profile_id),
        tenant_id=data.get("tenant_id", "tenant"),
        device_id=data.get("device_id", "cloud"),
        ts=datetime.now(tz=UTC),
        entity_type="profile",
        entity_id=str(profile_id),
        op="upsert",
        patch=data.get("patch", {}),
        vector=VectorClock(device="cloud", counter=int(len(state.events) + 1)),
        actor=data.get("actor", "api"),
    )
    state.ingest(event.to_json_line())
    return web.json_response({"ok": True, "profile_id": profile_id})


def create_app() -> web.Application:
    app = web.Application()
    app["state"] = CloudState()
    app.router.add_post("/sync/up", handle_sync_up)
    app.router.add_get("/sync/down", handle_sync_down)
    app.router.add_get("/resolve", handle_resolve)
    app.router.add_route("GET", "/profiles", handle_profiles)
    app.router.add_route("POST", "/profiles", handle_profiles)
    return app


def main() -> None:
    app = create_app()
    web.run_app(app, port=8080)


if __name__ == "__main__":
    main()
