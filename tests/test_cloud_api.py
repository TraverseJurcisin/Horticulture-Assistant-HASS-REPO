from datetime import datetime

from fastapi.testclient import TestClient

from cloud.api.main import create_app
from custom_components.horticulture_assistant.cloudsync import SyncEvent, VectorClock

UTC = datetime.UTC


def _make_event(event_id: str, entity_id: str, patch: dict) -> SyncEvent:
    return SyncEvent(
        event_id=event_id,
        tenant_id="tenant-1",
        device_id="edge-1",
        ts=datetime(2025, 10, 20, 12, 0, tzinfo=UTC),
        entity_type="profile",
        entity_id=entity_id,
        op="upsert",
        patch=patch,
        vector=VectorClock(device="edge-1", counter=1),
        actor="tester",
    )


def _post_event(client: TestClient, event: SyncEvent) -> None:
    resp = client.post(
        "/sync/up",
        data=event.to_json_line(),
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resp.status_code == 200


def test_profile_detail_and_stats_resolution() -> None:
    app = create_app()
    client = TestClient(app)

    species_event = _make_event(
        "evt-species",
        "species-1",
        {
            "profile_id": "species-1",
            "profile_type": "species",
            "identity": {"name": "Blueberry"},
            "taxonomy": {"species": "Vaccinium"},
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.7}}},
            "tags": ["species"],
        },
    )
    _post_event(client, species_event)

    cultivar_event = _make_event(
        "evt-cultivar",
        "cultivar-1",
        {
            "profile_id": "cultivar-1",
            "profile_type": "line",
            "identity": {"name": "Tophat"},
            "parents": ["species-1"],
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.9}}},
            "local_overrides": {"targets": {"vpd": {"vegetative": 1.1}}},
            "general": {"name": "Tophat", "sensors": {"temp": "sensor.temp"}},
            "citations": [{"source": "manual", "title": "operator"}],
            "local_metadata": {"citation_map": {"targets.vpd.vegetative": {"mode": "manual"}}},
            "resolver_state": {"resolved_keys": ["targets.vpd.vegetative"]},
        },
    )
    _post_event(client, cultivar_event)

    stats_payload = {
        "profile_id": "species-1",
        "stats_version": "2024.10",
        "computed_at": "2025-10-19T00:00:00Z",
        "payload": {"targets": {"vpd": {"vegetative": 0.8}}},
        "contributions": [
            {
                "profile_id": "species-1",
                "child_id": "cultivar-1",
                "n_runs": 3,
                "weight": 0.75,
            }
        ],
    }
    resp = client.post("/stats", json=stats_payload, headers={"X-Tenant-ID": "tenant-1"})
    assert resp.status_code == 200
    assert resp.json()["acked"]

    detail_resp = client.get(
        "/profiles/cultivar-1",
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert detail_resp.status_code == 200
    profile = detail_resp.json()["profile"]
    assert profile["plant_id"] == "cultivar-1"
    targets = profile["resolved_targets"]["targets.vpd.vegetative"]
    assert targets["value"] == 1.1
    assert targets["annotation"]["overlay"] == 0.8
    assert targets["annotation"]["overlay_source_type"] == "computed_stats"
    assert profile["library"]["curated_targets"]["targets"]["vpd"]["vegetative"] == 0.9
    assert profile["local"]["local_overrides"]["targets"]["vpd"]["vegetative"] == 1.1
    assert profile["computed_stats"][0]["payload"]["targets"]["vpd"]["vegetative"] == 0.8

    resolve_resp = client.get(
        "/resolve",
        params={"profile": "cultivar-1", "field": "targets.vpd.vegetative"},
        headers={"X-Tenant-ID": "tenant-1"},
    )
    assert resolve_resp.status_code == 200
    resolved = resolve_resp.json()
    assert resolved["value"] == 1.1
    assert resolved["overlay"] == 0.8

    list_resp = client.get("/profiles", headers={"X-Tenant-ID": "tenant-1"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()["profiles"]) == 2
