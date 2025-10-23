import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.api import ChatApi
from custom_components.horticulture_assistant.const import CONF_API_KEY, DOMAIN
from custom_components.horticulture_assistant.profile.schema import FieldAnnotation, ResolvedTarget


@pytest.mark.asyncio
async def test_profile_http_views(hass, hass_client, enable_custom_integrations, monkeypatch):
    async def dummy_chat(self, *args, **kwargs):  # pragma: no cover - network guard
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(ChatApi, "chat", dummy_chat)

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = hass.data[DOMAIN][entry.entry_id]["profile_registry"]

    profile_id = await registry.async_add_profile("Heritage Tomato")
    await registry.async_record_run_event(
        profile_id,
        {
            "run_id": "run-1",
            "profile_id": profile_id,
            "species_id": None,
            "started_at": "2025-01-01T00:00:00Z",
            "ended_at": "2025-01-04T00:00:00Z",
            "environment": {"temperature_c": 21.5},
            "targets_met": 18,
            "targets_total": 20,
            "stress_events": 2,
        },
    )
    await registry.async_record_harvest_event(
        profile_id,
        {
            "harvest_id": "harvest-1",
            "profile_id": profile_id,
            "harvested_at": "2025-01-10T00:00:00Z",
            "yield_grams": 120.5,
            "area_m2": 2.5,
        },
    )

    profile = registry.get_profile(profile_id)
    annotation = FieldAnnotation(source_type="manual", method="manual")
    profile.resolved_targets["vpd_max"] = ResolvedTarget(value=1.2, annotation=annotation, citations=[])
    profile.refresh_sections()
    await registry.async_save()

    client = await hass_client()

    response = await client.get("/api/horticulture_assistant/profiles")
    assert response.status == 200
    payload = await response.json()
    summaries = {item["profile_id"]: item for item in payload["profiles"]}
    assert profile_id in summaries
    assert summaries[profile_id]["name"] == "Heritage Tomato"
    assert summaries[profile_id]["targets"]["vpd_max"] == pytest.approx(1.2)
    provenance = summaries[profile_id]["provenance"]["vpd_max"]
    assert provenance["source_type"] == "manual"
    assert not provenance.get("is_inherited")
    assert summaries[profile_id]["computed_stats"]
    success_summary = summaries[profile_id].get("success")
    assert success_summary is not None
    assert success_summary["weighted_percent"] == pytest.approx(90.0)
    assert success_summary["samples_recorded"] == 1

    detail_resp = await client.get(f"/api/horticulture_assistant/profiles/{profile_id}")
    assert detail_resp.status == 200
    detail = await detail_resp.json()
    assert detail["profile_id"] == profile_id
    assert "resolved_targets" in detail and "vpd_max" in detail["resolved_targets"]
    assert detail["resolved_targets"]["vpd_max"]["value"] == pytest.approx(1.2)
    assert detail["resolved_provenance"]["vpd_max"]["source_type"] == "manual"
    assert detail["provenance_summary"]["vpd_max"]["value"] == pytest.approx(1.2)
    assert any(snap["stats_version"] == "environment/v1" for snap in detail["computed_stats"])
    assert any(snap["stats_version"] == "success/v1" for snap in detail["computed_stats"])

    target_resp = await client.get(f"/api/horticulture_assistant/profiles/{profile_id}/targets/vpd_max")
    assert target_resp.status == 200
    target_payload = await target_resp.json()
    assert target_payload["profile_id"] == profile_id
    assert target_payload["target"]["value"] == pytest.approx(1.2)
    assert target_payload["target"]["annotation"]["source_type"] == "manual"
    assert target_payload["target"]["provenance"]["source_type"] == "manual"

    missing_resp = await client.get(f"/api/horticulture_assistant/profiles/{profile_id}/targets/missing")
    assert missing_resp.status == 404

    unknown_resp = await client.get("/api/horticulture_assistant/profiles/does-not-exist")
    assert unknown_resp.status == 404
