from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response

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
GLOBAL_TENANTS = {"public", "shared", "global"}


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
        self.entities: dict[tuple[str, str, str], CloudEntity] = {}
        self.conflicts = ConflictResolver()
        self.cursor = 0
        self.public_tenants = {tenant.lower() for tenant in GLOBAL_TENANTS}

    # ------------------------------------------------------------------
    def ingest(self, ndjson_payload: str, *, tenant_id: str) -> list[str]:
        events = decode_ndjson(ndjson_payload)
        acked: list[str] = []
        request_tenant = tenant_id.lower()
        for event in events:
            event_tenant_raw = str(event.tenant_id)
            event_tenant = event_tenant_raw.lower()
            if event_tenant != request_tenant and event_tenant not in self.public_tenants:
                raise ValueError(f"event tenant {event_tenant_raw} does not match request tenant {tenant_id}")
            self.cursor += 1
            event.metadata.setdefault("cursor", self.cursor)
            acked.append(event.event_id)
            self.events.append(event)
            key = (event_tenant, event.entity_type, event.entity_id)
            current = self.entities.get(key)
            payload = current.payload if current else {}
            merged = self.conflicts.apply(payload, event)
            merged.pop("__meta__", None)
            self.entities[key] = CloudEntity(
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                tenant_id=event_tenant_raw,
                payload=merged,
                updated_at=event.ts,
            )
        return acked

    def stream(self, cursor: int | None, *, tenant_id: str) -> tuple[str, int | None]:
        start = 0 if cursor is None else cursor
        pending = [
            event
            for event in self.events
            if event.metadata.get("cursor", 0) > start and self._event_visible(event, tenant_id)
        ]
        if not pending:
            return "", cursor
        ndjson_payload = encode_ndjson(pending)
        next_cursor = pending[-1].metadata.get("cursor")
        return ndjson_payload, int(next_cursor) if next_cursor is not None else cursor

    def resolve(self, tenant_id: str, profile_id: str, field: str) -> Mapping[str, Any]:
        profile_payload = self._get_entity("profile", profile_id, tenant_id)
        if not profile_payload:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        store = EdgeSyncStore(":memory:")
        store.update_cloud_cache(
            "profile",
            profile_id,
            str(profile_payload.tenant_id),
            profile_payload.payload,
        )
        parents = profile_payload.payload.get("parents") or []
        for parent_id in parents:
            parent_payload = self._get_entity("profile", str(parent_id), tenant_id)
            if parent_payload:
                store.update_cloud_cache(
                    "profile",
                    str(parent_id),
                    str(parent_payload.tenant_id),
                    parent_payload.payload,
                )
        species_id = str(parents[-1]) if parents else profile_id
        stats_payload = self._get_entity("computed", species_id, tenant_id)
        if stats_payload:
            store.update_cloud_cache(
                "computed",
                species_id,
                str(stats_payload.tenant_id),
                stats_payload.payload,
            )
        resolver = EdgeResolverService(store)
        result = resolver.resolve_field(profile_id, field)
        return {
            "value": result.value,
            "provenance": result.provenance,
            "overlay": result.overlay,
            "overlay_provenance": result.overlay_provenance,
            "staleness_days": result.staleness_days,
            "annotations": asdict(result.annotations),
        }

    def list_profiles(self, tenant_id: str, profile_type: str | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for entity in self.entities.values():
            if entity.entity_type != "profile":
                continue
            if not self._tenant_visible(entity.tenant_id, tenant_id):
                continue
            if profile_type and entity.payload.get("profile_type") != profile_type:
                continue
            item = asdict(entity)
            item["updated_at"] = entity.updated_at.isoformat()
            items.append(item)
        return items

    def _event_visible(self, event: SyncEvent, tenant_id: str) -> bool:
        normalized = tenant_id.lower()
        event_tenant = str(event.tenant_id).lower()
        if event_tenant == normalized:
            return True
        return event_tenant in self.public_tenants

    def _tenant_visible(self, entity_tenant: str, tenant_id: str) -> bool:
        entity_norm = str(entity_tenant).lower()
        tenant_norm = tenant_id.lower()
        if entity_norm == tenant_norm:
            return True
        return entity_norm in self.public_tenants

    def _get_entity(self, entity_type: str, entity_id: str, tenant_id: str) -> CloudEntity | None:
        key = (tenant_id.lower(), entity_type, entity_id)
        entity = self.entities.get(key)
        if entity:
            return entity
        for candidate in self.public_tenants:
            entity = self.entities.get((candidate, entity_type, entity_id))
            if entity:
                return entity
        return None


def create_app() -> FastAPI:
    app = FastAPI()
    state = CloudState()
    app.state.state = state

    @app.post("/sync/up")
    async def handle_sync_up(
        request: Request,
        tenant: str = Header(..., alias="X-Tenant-ID"),
    ) -> dict[str, Any]:
        payload = (await request.body()).decode()
        if not payload.strip():
            return {"acked": []}
        try:
            acked = state.ingest(payload, tenant_id=tenant)
        except ValueError as err:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=str(err)) from err
        return {"acked": acked}

    @app.get("/sync/down")
    async def handle_sync_down(
        tenant: str = Header(..., alias="X-Tenant-ID"),
        cursor: int | None = Query(None),
    ) -> Response:
        ndjson_payload, next_cursor = state.stream(cursor, tenant_id=tenant)
        if not ndjson_payload:
            return Response(status_code=204)
        headers: dict[str, str] = {}
        if next_cursor is not None:
            headers["X-Sync-Cursor"] = str(next_cursor)
        return Response(content=ndjson_payload, media_type="application/x-ndjson", headers=headers)

    @app.get("/resolve")
    async def handle_resolve(
        tenant: str = Header(..., alias="X-Tenant-ID"),
        profile: str = Query(...),
        field: str = Query(...),
    ) -> Mapping[str, Any]:
        return state.resolve(tenant, profile, field)

    @app.get("/profiles")
    async def handle_profiles(
        tenant: str = Header(..., alias="X-Tenant-ID"),
        profile_type: str | None = Query(None, alias="type"),
    ) -> dict[str, Any]:
        items = state.list_profiles(tenant, profile_type)
        return {"profiles": items}

    @app.post("/profiles")
    async def handle_profiles_post(
        data: dict[str, Any],
        tenant: str = Header(..., alias="X-Tenant-ID"),
    ) -> dict[str, Any]:
        profile_id = data.get("profile_id")
        if not profile_id:
            raise HTTPException(status_code=400, detail="profile_id required")
        event = SyncEvent(
            event_id=str(data.get("event_id", profile_id)),
            tenant_id=str(data.get("tenant_id", tenant)),
            device_id=str(data.get("device_id", "cloud")),
            ts=datetime.now(tz=UTC),
            entity_type="profile",
            entity_id=str(profile_id),
            op=str(data.get("op", "upsert")),
            patch=data.get("patch", {}),
            vector=VectorClock(device="cloud", counter=int(len(state.events) + 1)),
            actor=str(data.get("actor", "api")),
        )
        acked = state.ingest(event.to_json_line(), tenant_id=tenant)
        return {"acked": acked, "profile_id": profile_id}

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
