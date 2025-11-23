from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.cloudsync import (
    CloudAuthError,
    CloudAuthTokens,
    CloudSyncConfig,
    CloudSyncError,
    CloudSyncManager,
    ConflictPolicy,
    ConflictResolver,
    EdgeResolverService,
    EdgeSyncStore,
    EdgeSyncWorker,
    SyncEvent,
    VectorClock,
    resolve_result_to_resolved_target,
)
from custom_components.horticulture_assistant.const import (
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_ACCOUNT_EMAIL,
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_ORGANIZATION_ID,
    CONF_CLOUD_ORGANIZATION_NAME,
    CONF_CLOUD_ORGANIZATION_ROLE,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_SYNC_INTERVAL,
    CONF_CLOUD_TENANT_ID,
    CONF_CLOUD_TOKEN_EXPIRES_AT,
    DOMAIN,
)

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017


def make_event(event_id: str, entity_type: str, patch: dict, *, org_id: str | None = "org-1") -> SyncEvent:
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
        org_id=org_id,
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


def test_cloud_auth_tokens_parses_numeric_expiry() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    payload = {
        "access_token": "abc123",
        "tenant_id": "tenant-1",
        "expires_at": "3600",
    }

    tokens = CloudAuthTokens.from_payload(payload, now=now)

    assert tokens.expires_at == now + timedelta(seconds=3600)


def test_edge_store_list_cloud_cache(tmp_path: Path) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    payload = {"curated_targets": {"targets": {"vpd": {"vegetative": 0.9}}}}
    store.update_cloud_cache("profile", "cultivar-1", "tenant-1", payload, org_id="org-1")
    items = store.list_cloud_cache("profile", org_id="org-1")
    assert len(items) == 1
    entry = items[0]
    assert entry["entity_id"] == "cultivar-1"
    assert entry["tenant_id"] == "tenant-1"
    assert entry["org_id"] == "org-1"
    assert entry["payload"]["curated_targets"]["targets"]["vpd"]["vegetative"] == 0.9


def test_edge_store_cloud_cache_age(tmp_path: Path, monkeypatch) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    base = datetime(2025, 10, 20, tzinfo=UTC)

    class DummyDateTime(datetime):
        current = base

        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            return cls.current

    from custom_components.horticulture_assistant.cloudsync import edge_store as edge_store_module

    monkeypatch.setattr(edge_store_module, "datetime", DummyDateTime)

    DummyDateTime.current = base - timedelta(days=3)
    store.update_cloud_cache("profile", "cultivar-1", "tenant-1", {"value": 1}, org_id="org-1")

    DummyDateTime.current = base - timedelta(days=1)
    store.update_cloud_cache("computed", "species-1", "tenant-1", {"payload": {"value": 2}}, org_id="org-2")

    age_latest = store.cloud_cache_age(now=base)
    age_oldest = store.cloud_cache_oldest_age(now=base)

    assert store.count_cloud_cache() == 2
    assert store.outbox_size() == 0
    assert age_latest == pytest.approx(1.0, rel=1e-3)
    assert age_oldest == pytest.approx(3.0, rel=1e-3)


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
    store.update_cloud_cache("profile", "cultivar-1", "tenant-1", profile_event.patch, org_id="org-1")
    species_event = make_event(
        "01JC",
        "profile",
        {"curated_targets": {"targets": {"vpd": {"vegetative": 0.7}}}, "parents": []},
    )
    store.update_cloud_cache("profile", "species-1", "tenant-1", species_event.patch, org_id="org-1")
    snapshot = {
        "stats_version": "environment/v1",
        "computed_at": "2025-10-19T00:00:00Z",
        "snapshot_id": "species-1:environment/v1",
        "payload": {"targets": {"vpd": {"vegetative": 0.8}}, "scope": "species"},
        "contributions": [],
    }
    stats_payload = {
        "profile_id": "species-1",
        "profile_type": "species",
        "species_id": "species-1",
        "computed_at": snapshot["computed_at"],
        "versions": {snapshot["stats_version"]: snapshot},
        "snapshots": {snapshot["snapshot_id"]: snapshot},
        "latest_versions": {snapshot["stats_version"]: snapshot["snapshot_id"]},
    }
    store.update_cloud_cache("computed", "species-1", "tenant-1", stats_payload, org_id="org-1")

    def local_loader(pid: str) -> dict:
        if pid == "cultivar-1":
            return {"curated_targets": {"targets": {"vpd": {"vegetative": 1.1}}}}
        return {}

    resolver = EdgeResolverService(
        store,
        local_profile_loader=local_loader,
        tenant_id="tenant-1",
        organization_id="org-1",
    )
    result = resolver.resolve_field("cultivar-1", "targets.vpd.vegetative", now=datetime(2025, 10, 20, tzinfo=UTC))
    assert result.value == 1.1
    assert result.overlay == 0.8
    assert result.provenance[0] == "local:cultivar-1"
    assert result.overlay_provenance == ["computed:species-1"]
    assert result.annotations.source_type == "local_override"
    assert result.annotations.source_ref == ["cultivar-1"]
    assert result.annotations.method == "inheritance"
    assert result.annotations.overlay_source_type == "computed_stats"
    assert result.annotations.overlay_source_ref == ["species-1"]
    assert result.annotations.overlay_method == "data_driven"
    assert result.annotations.staleness_days == pytest.approx(1.0)
    assert not result.annotations.is_stale

    resolved_target = resolve_result_to_resolved_target(result)
    assert resolved_target.value == 1.1
    assert resolved_target.annotation.overlay == 0.8
    assert resolved_target.annotation.overlay_source_type == "computed_stats"
    assert resolved_target.annotation.extras["provenance"] == ["local:cultivar-1"]

    direct_target = resolver.resolve_target(
        "cultivar-1", "targets.vpd.vegetative", now=datetime(2025, 10, 20, tzinfo=UTC)
    )
    assert direct_target.value == 1.1
    assert direct_target.annotation.overlay == 0.8


def test_edge_resolver_marks_stale_stats(tmp_path: Path) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    species_payload = {"curated_targets": {"targets": {"vpd": {"vegetative": 0.75}}}, "parents": []}
    store.update_cloud_cache("profile", "species-1", "tenant-1", species_payload, org_id="org-1")
    stale_snapshot = {
        "stats_version": "environment/v1",
        "computed_at": "2024-01-01T00:00:00Z",
        "snapshot_id": "species-1:environment/v1",
        "payload": {"targets": {"vpd": {"vegetative": 0.7}}, "scope": "species"},
        "contributions": [],
    }
    stale_payload = {
        "profile_id": "species-1",
        "profile_type": "species",
        "species_id": "species-1",
        "computed_at": stale_snapshot["computed_at"],
        "versions": {stale_snapshot["stats_version"]: stale_snapshot},
        "snapshots": {stale_snapshot["snapshot_id"]: stale_snapshot},
        "latest_versions": {stale_snapshot["stats_version"]: stale_snapshot["snapshot_id"]},
    }
    store.update_cloud_cache("computed", "species-1", "tenant-1", stale_payload, org_id="org-1")
    resolver = EdgeResolverService(
        store,
        stats_ttl=timedelta(days=30),
        tenant_id="tenant-1",
        organization_id="org-1",
    )
    result = resolver.resolve_field("species-1", "targets.vpd.vegetative", now=datetime(2024, 3, 15, tzinfo=UTC))
    assert result.value == 0.75
    assert result.overlay == 0.7
    assert result.annotations.is_stale
    assert result.annotations.staleness_days == pytest.approx(74.0, rel=1e-2)


def test_edge_resolver_resolve_profile(tmp_path: Path) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    cultivar_payload = {
        "profile_id": "cultivar-1",
        "profile_type": "line",
        "parents": ["species-1"],
        "identity": {"name": "Tophat"},
        "curated_targets": {"targets": {"vpd": {"vegetative": 0.9}}},
    }
    store.update_cloud_cache("profile", "cultivar-1", "tenant-1", cultivar_payload, org_id="org-1")
    species_payload = {
        "profile_id": "species-1",
        "profile_type": "species",
        "curated_targets": {"targets": {"vpd": {"vegetative": 0.7}}},
        "parents": [],
    }
    store.update_cloud_cache("profile", "species-1", "tenant-1", species_payload, org_id="org-1")
    stats_payload = {
        "computed_at": "2025-10-19T00:00:00Z",
        "payload": {"targets": {"vpd": {"vegetative": 0.8}}},
    }
    store.update_cloud_cache("computed", "species-1", "tenant-1", stats_payload, org_id="org-1")

    local_payload = {
        "general": {"name": "Tophat"},
        "local_overrides": {"targets": {"vpd": {"vegetative": 1.1}}},
        "resolver_state": {"resolved_keys": ["targets.vpd.vegetative"]},
        "citations": [{"source": "manual", "title": "operator"}],
    }

    def local_loader(pid: str) -> dict:
        if pid == "cultivar-1":
            return dict(local_payload)
        return {}

    resolver = EdgeResolverService(
        store,
        local_profile_loader=local_loader,
        tenant_id="tenant-1",
        organization_id="org-1",
    )
    profile = resolver.resolve_profile(
        "cultivar-1",
        now=datetime(2025, 10, 20, tzinfo=UTC),
        local_payload=local_payload,
    )

    target = profile.resolved_targets["targets.vpd.vegetative"]
    assert target.value == 1.1
    assert target.annotation.overlay == 0.8
    assert profile.library_section().curated_targets["targets"]["vpd"]["vegetative"] == 0.9
    assert profile.computed_stats[0].payload["targets"]["vpd"]["vegetative"] == 0.8
    assert profile.general["name"] == "Tophat"


def test_edge_resolver_respects_tenant(tmp_path: Path) -> None:
    store = EdgeSyncStore(tmp_path / "sync.db")
    store.update_cloud_cache(
        "profile",
        "species-1",
        "tenant-1",
        {"profile_type": "species", "curated_targets": {"targets": {"vpd": {"vegetative": 0.75}}}},
        org_id="org-tenant-1",
    )
    store.update_cloud_cache(
        "profile",
        "cultivar-1",
        "tenant-1",
        {
            "profile_type": "line",
            "parents": ["species-1"],
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.8}}},
        },
        org_id="org-tenant-1",
    )
    store.update_cloud_cache(
        "profile",
        "species-1",
        "tenant-2",
        {"profile_type": "species", "curated_targets": {"targets": {"vpd": {"vegetative": 0.55}}}},
        org_id="org-tenant-2",
    )
    store.update_cloud_cache(
        "profile",
        "cultivar-1",
        "tenant-2",
        {
            "profile_type": "line",
            "parents": ["species-1"],
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.6}}},
        },
        org_id="org-tenant-2",
    )

    resolver_tenant_one = EdgeResolverService(
        store,
        tenant_id="tenant-1",
        organization_id="org-tenant-1",
    )
    resolver_tenant_two = EdgeResolverService(
        store,
        tenant_id="tenant-2",
        organization_id="org-tenant-2",
    )

    result_one = resolver_tenant_one.resolve_field("cultivar-1", "targets.vpd.vegetative")
    result_two = resolver_tenant_two.resolve_field("cultivar-1", "targets.vpd.vegetative")

    assert result_one.value == 0.8
    assert result_two.value == 0.6


@pytest.mark.parametrize(
    "body, content_type, expected_cursor, expected_payload",
    [
        (
            json.dumps({"events": "{}", "cursor": "abc"}).encode(),
            "application/json",
            "abc",
            "{}",
        ),
        (
            json.dumps({"events": [{"event_id": "1"}, {"event_id": "2"}], "cursor": "xyz"}).encode(),
            "application/json",
            "xyz",
            (
                json.dumps({"event_id": "1"}, separators=(",", ":"))
                + "\n"
                + json.dumps({"event_id": "2"}, separators=(",", ":"))
            ),
        ),
        (b"{ }\n{ }", "application/x-ndjson", "next", "{ }\n{ }"),
    ],
)
def test_edge_worker_response_parsing(
    body: bytes, content_type: str, expected_cursor: str | None, expected_payload: str
) -> None:
    store = EdgeSyncStore(":memory:")
    worker = EdgeSyncWorker(
        store,
        cast(ClientSession, object()),
        "https://api.example",
        "token",
        "tenant",
        organization_id="org-1",
    )
    ndjson, cursor = worker._parse_down_response(body, content_type, {"X-Sync-Cursor": "next"})
    assert ndjson == expected_payload
    assert cursor == expected_cursor


@pytest.mark.asyncio
async def test_cloud_sync_manager_disabled(hass, tmp_path):
    entry = MockConfigEntry(domain=DOMAIN, entry_id="entry", data={}, options={})
    manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync.db")
    await manager.async_start()
    status = manager.status()
    assert status["enabled"] is False
    assert status["configured"] is False
    assert status["cloud_snapshot_age_days"] is None
    assert status["connection"]["configured"] is False
    assert status["connection"]["local_only"] is True
    await manager.async_stop()


@pytest.mark.asyncio
async def test_cloud_sync_manager_starts_worker(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry2",
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "token",
            CONF_CLOUD_SYNC_INTERVAL: 60,
        },
    )
    session = MagicMock()
    session.close = AsyncMock()
    worker = MagicMock()
    worker.run_forever = AsyncMock()
    worker.status.return_value = {"cursor": "abc"}

    with (
        patch(
            "custom_components.horticulture_assistant.cloudsync.manager.ClientSession",
            return_value=session,
        ),
        patch(
            "custom_components.horticulture_assistant.cloudsync.manager.EdgeSyncWorker",
            return_value=worker,
        ),
    ):
        manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync2.db")
        await manager.async_start()
        await asyncio.sleep(0)
        status = manager.status(now=datetime(2025, 1, 1, tzinfo=UTC))
        assert status["enabled"] is True
        assert status["configured"] is True
        assert status["cursor"] == "abc"
        assert status["outbox_size"] == 0
        assert status["cloud_cache_entries"] == 0
        assert status["connection"]["configured"] is True
        assert status["connection"]["connected"] is False
        assert status["connection"]["reason"] == "never_synced"
        worker.run_forever.assert_awaited()
        await manager.async_stop()
        session.close.assert_awaited()


@pytest.mark.asyncio
async def test_cloud_manager_update_tokens_notifies_listeners(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "device-1",
        },
    )
    entry.add_to_hass(hass)
    manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync.db")

    listener_calls: list[dict[str, Any]] = []

    async def _listener(opts):
        listener_calls.append(dict(opts))

    manager.register_token_listener(_listener)

    tokens = CloudAuthTokens(
        access_token="token-new",
        refresh_token="refresh-new",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        tenant_id="tenant-1",
        device_token="device-2",
        account_email="user@example.com",
        roles=("premium",),
        organization_id="org-1",
        organization_name="Org One",
        organization_role="admin",
    )

    with patch.object(manager, "async_refresh", AsyncMock()) as refresh:
        opts = await manager.async_update_tokens(tokens, base_url="https://cloud.example")

    assert entry.options[CONF_CLOUD_ACCESS_TOKEN] == "token-new"
    assert entry.options[CONF_CLOUD_REFRESH_TOKEN] == "refresh-new"
    assert entry.options[CONF_CLOUD_DEVICE_TOKEN] == "device-2"
    assert entry.options[CONF_CLOUD_ACCOUNT_EMAIL] == "user@example.com"
    assert entry.options[CONF_CLOUD_ACCOUNT_ROLES] == ["premium"]
    assert entry.options[CONF_CLOUD_ORGANIZATION_ID] == "org-1"
    assert entry.options[CONF_CLOUD_ORGANIZATION_NAME] == "Org One"
    assert entry.options[CONF_CLOUD_ORGANIZATION_ROLE] == "admin"
    assert entry.options[CONF_CLOUD_TOKEN_EXPIRES_AT].startswith("2026-01-01")
    refresh.assert_awaited()
    assert listener_calls
    assert listener_calls[0][CONF_CLOUD_ACCESS_TOKEN] == "token-new"
    assert opts[CONF_CLOUD_ORGANIZATION_NAME] == "Org One"


@pytest.mark.asyncio
async def test_cloud_manager_trigger_refresh_records_errors(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_REFRESH_TOKEN: "refresh-old",
            CONF_CLOUD_ACCESS_TOKEN: "access-old",
        },
    )
    entry.add_to_hass(hass)
    manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync.db")
    manager.config = CloudSyncConfig.from_options(entry.options)

    with (
        patch(
            "custom_components.horticulture_assistant.cloudsync.manager.CloudAuthClient.async_refresh",
            AsyncMock(side_effect=CloudAuthError("boom")),
        ),
        pytest.raises(CloudAuthError),
    ):
        await manager.async_trigger_token_refresh(force=True)

    status = manager.status()
    assert status["last_token_refresh_error"] == "boom"
    assert status["last_token_refresh_at"] is not None


@pytest.mark.asyncio
async def test_cloud_manager_auto_refresh_schedules_task(hass, tmp_path):
    future = datetime.now(tz=UTC) + timedelta(hours=2)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "device-1",
            CONF_CLOUD_ACCESS_TOKEN: "access",
            CONF_CLOUD_REFRESH_TOKEN: "refresh",
            CONF_CLOUD_TOKEN_EXPIRES_AT: future.isoformat(),
        },
    )
    entry.add_to_hass(hass)
    with patch("custom_components.horticulture_assistant.cloudsync.manager.EdgeSyncWorker") as worker_cls:
        worker = MagicMock()
        worker.run_forever = AsyncMock()
        worker_cls.return_value = worker
        manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync.db")
        await manager.async_start()
        status = manager.status()
        assert status["next_token_refresh_at"] is not None
        await manager.async_stop()


@pytest.mark.asyncio
async def test_cloud_manager_sync_now_runs_single_cycle(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "device-1",
        },
    )
    entry.add_to_hass(hass)
    manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync_manual.db")

    session = MagicMock()
    session.close = AsyncMock()
    worker = MagicMock()
    worker.push_once = AsyncMock(return_value=2)
    worker.pull_once = AsyncMock(return_value=4)
    worker.status.return_value = {}

    with (
        patch("custom_components.horticulture_assistant.cloudsync.manager.ClientSession", return_value=session),
        patch("custom_components.horticulture_assistant.cloudsync.manager.EdgeSyncWorker", return_value=worker),
    ):
        result = await manager.async_sync_now()

    worker.push_once.assert_awaited()
    worker.pull_once.assert_awaited()
    session.close.assert_awaited()
    assert result["pushed"] == 2
    assert result["pulled"] == 4
    manual = result["status"].get("manual_sync")
    assert manual and manual["result"] == {"pushed": 2, "pulled": 4}
    assert manual["last_run_at"] is not None


@pytest.mark.asyncio
async def test_cloud_manager_sync_now_requires_ready(hass, tmp_path):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync_manual.db")
    with pytest.raises(CloudSyncError):
        await manager.async_sync_now()


@pytest.mark.asyncio
async def test_cloud_manager_sync_now_validates_directions(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "device-1",
        },
    )
    entry.add_to_hass(hass)
    manager = CloudSyncManager(hass, entry, store_path=tmp_path / "sync_manual.db")
    with pytest.raises(CloudSyncError):
        await manager.async_sync_now(push=False, pull=False)
