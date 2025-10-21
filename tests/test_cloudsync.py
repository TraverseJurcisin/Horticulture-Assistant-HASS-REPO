from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import cast

import pytest

from aiohttp import ClientSession

from custom_components.horticulture_assistant.cloudsync import (
    ConflictPolicy,
    ConflictResolver,
    EdgeResolverService,
    EdgeSyncStore,
    EdgeSyncWorker,
    SyncEvent,
    VectorClock,
)


UTC = getattr(datetime, "UTC", timezone.utc)


def make_event(event_id: str, entity_type: str, patch: dict) -> SyncEvent:
    return SyncEvent(
        event_id=event_id,
        tenant_id="tenant-1",
        device_id="edge-1",
        ts=datetime(2025, 10, 20, 12, 3, 14, tzinfo=UTC),
        entity_type=entity_type,
        entity_id="entity-1",
        op="upsert",
        patch=patch,
        vector=VectorClock(device="edge-1", counter=1),
        actor="tester",
    )


def test_event_roundtrip() -> None:
    event = make_event("01J8", "profile", {"curated_targets": {"foo": 1}})
    encoded = event.to_json_line()
    decoded = SyncEvent.from_json_line(encoded)
    assert decoded.event_id == event.event_id
    assert decoded.patch == event.patch


def test_edge_store_outbox(tmp_path: Path) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    event = make_event("01J9", "profile", {"value": 1})
    store.append_outbox(event)
    batch = store.get_outbox_batch()
    assert len(batch) == 1
    assert batch[0].event_id == "01J9"
    store.mark_outbox_attempt(["01J9"])
    store.mark_outbox_acked(["01J9"])
    assert store.get_outbox_batch() == []


def test_conflict_resolver_or_set() -> None:
    resolver = ConflictResolver(field_policies={"tags": ConflictPolicy.OR_SET})
    initial = {"tags": ["a"]}
    event = make_event("01JA", "profile", {"tags": {"add": ["b", "c"], "remove": ["a"]}})
    merged = resolver.apply(initial, event)
    assert sorted(merged["tags"]) == ["b", "c"]


def test_edge_resolver_prefers_local_override(tmp_path: Path) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    profile_event = make_event(
        "01JB",
        "profile",
        {
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.9}}},
            "parents": ["species-1"],
        },
    )
    store.update_cloud_cache("profile", "cultivar-1", "tenant-1", profile_event.patch)
    species_event = make_event(
        "01JC",
        "profile",
        {"curated_targets": {"targets": {"vpd": {"vegetative": 0.7}}}, "parents": []},
    )
    store.update_cloud_cache("profile", "species-1", "tenant-1", species_event.patch)
    stats_payload = {
        "computed_at": "2025-10-19T00:00:00Z",
        "payload": {"targets": {"vpd": {"vegetative": 0.8}}},
    }
    store.update_cloud_cache("computed", "species-1", "tenant-1", stats_payload)

    def local_loader(pid: str) -> dict:
        if pid == "cultivar-1":
            return {"curated_targets": {"targets": {"vpd": {"vegetative": 1.1}}}}
        return {}

    resolver = EdgeResolverService(store, local_profile_loader=local_loader)
    result = resolver.resolve_field("cultivar-1", "targets.vpd.vegetative", now=datetime(2025, 10, 20, tzinfo=UTC))
    assert result.value == 1.1
    assert result.overlay == 0.8
    assert result.provenance[0] == "local:cultivar-1"
    assert result.overlay_provenance == ["computed:species-1"]


@pytest.mark.parametrize(
    "body, content_type, expected_cursor",
    [
        (json.dumps({"events": "{}", "cursor": "abc"}).encode(), "application/json", "abc"),
        (b"{ }\n{ }", "application/x-ndjson", "next"),
    ],
)
def test_edge_worker_response_parsing(body: bytes, content_type: str, expected_cursor: str | None) -> None:
    store = EdgeSyncStore(":memory:")
    worker = EdgeSyncWorker(store, cast(ClientSession, object()), "https://api.example", "token", "tenant")
    ndjson, cursor = worker._parse_down_response(body, content_type, {"X-Sync-Cursor": "next"})
    if content_type.startswith("application/json"):
        assert ndjson == "{}"
    else:
        assert ndjson == "{ }\n{ }"
    assert cursor == expected_cursor

