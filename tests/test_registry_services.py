import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError

from custom_components.horticulture_assistant.cloudsync.auth import CloudAuthTokens, CloudOrganization
from custom_components.horticulture_assistant.cloudsync.manager import CloudSyncError
from custom_components.horticulture_assistant.const import (
    CONF_API_KEY,
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_ACCOUNT_EMAIL,
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_AVAILABLE_ORGANIZATIONS,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_ORGANIZATION_ID,
    CONF_CLOUD_ORGANIZATION_NAME,
    CONF_CLOUD_ORGANIZATION_ROLE,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_TENANT_ID,
    CONF_CLOUD_TOKEN_EXPIRES_AT,
    DOMAIN,
)
from custom_components.horticulture_assistant.profile.schema import FieldAnnotation, ResolvedTarget
from custom_components.horticulture_assistant.profile.statistics import EVENT_STATS_VERSION, NUTRIENT_STATS_VERSION
from custom_components.horticulture_assistant.services import er
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def _setup_entry_with_profile(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1", "sensors": {"moisture": "sensor.old"}}}},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with (
        patch.object(hca, "HortiAICoordinator") as mock_ai,
        patch.object(hca, "HortiLocalCoordinator") as mock_local,
    ):
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    return entry


async def test_replace_sensor_updates_registry(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    reg = er.async_get(hass)
    reg.async_get_or_create("sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture")
    reg.async_get_or_create(
        "sensor",
        "test",
        "sensor_good",
        suggested_object_id="good",
        original_device_class="moisture",
    )
    hass.states.async_set("sensor.old", 1)
    hass.states.async_set("sensor.good", 2)

    await hass.services.async_call(
        DOMAIN,
        "replace_sensor",
        {"profile_id": "p1", "measurement": "moisture", "entity_id": "sensor.good"},
        blocking=True,
    )
    await hass.async_block_till_done()
    registry = hass.data[DOMAIN]["registry"]
    prof = registry.get("p1")
    assert prof.general["sensors"]["moisture"] == "sensor.good"
    assert entry.options["profiles"]["p1"]["sensors"]["moisture"] == "sensor.good"


async def test_replace_sensor_invalid_measurement(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    hass.states.async_set("sensor.some", 1)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "replace_sensor",
            {"profile_id": "p1", "measurement": "bad", "entity_id": "sensor.some"},
            blocking=True,
        )


async def test_refresh_species_sets_flag(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    await hass.services.async_call(DOMAIN, "refresh_species", {"profile_id": "p1"}, blocking=True)
    from custom_components.horticulture_assistant.profile.store import async_get_profile

    prof = await async_get_profile(hass, "p1")
    assert prof["last_resolved"] == "1970-01-01T00:00:00Z"
    assert entry.options["profiles"]["p1"]["name"] == "Plant 1"


async def test_export_profiles_service_writes_file(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    out = tmp_path / "profiles.json"
    await hass.services.async_call(DOMAIN, "export_profiles", {"path": str(out)}, blocking=True)
    data = json.loads(out.read_text())
    assert data[0]["plant_id"] == "p1"


async def test_export_profiles_relative_path_uses_config(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    rel = "profiles_rel.json"
    await hass.services.async_call(DOMAIN, "export_profiles", {"path": rel}, blocking=True)
    assert Path(hass.config.path(rel)).exists()


async def test_replace_sensor_missing_entity(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "replace_sensor",
            {"profile_id": "p1", "measurement": "moisture", "entity_id": "sensor.miss"},
            blocking=True,
        )


async def test_replace_sensor_device_class_mismatch(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    reg = er.async_get(hass)
    reg.async_get_or_create("sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture")
    reg.async_get_or_create(
        "sensor",
        "test",
        "sensor_temp",
        suggested_object_id="temp",
        original_device_class="temperature",
    )
    hass.states.async_set("sensor.temp", 1)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "replace_sensor",
            {"profile_id": "p1", "measurement": "moisture", "entity_id": "sensor.temp"},
            blocking=True,
        )


async def test_refresh_species_unknown_profile(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    with pytest.raises(ValueError):
        await hass.services.async_call(DOMAIN, "refresh_species", {"profile_id": "unknown"}, blocking=True)


async def test_export_profiles_creates_parent_dir(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    nested = tmp_path / "nested" / "profiles.json"
    await hass.services.async_call(DOMAIN, "export_profiles", {"path": str(nested)}, blocking=True)
    assert nested.exists()


async def test_replace_sensor_unknown_profile(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    with pytest.raises(ValueError):
        await hass.services.async_call(
            DOMAIN,
            "replace_sensor",
            {"profile_id": "missing", "measurement": "moisture", "entity_id": "sensor.old"},
            blocking=True,
        )


async def test_refresh_species_persists_storage(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    await hass.services.async_call(DOMAIN, "refresh_species", {"profile_id": "p1"}, blocking=True)
    store_file = Path(hass.config.path("horticulture_assistant/profiles/p1.json"))
    assert store_file.exists()
    data = json.loads(store_file.read_text())
    assert data["plant_id"] == "p1"


async def test_record_run_event_service_updates_history(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    response = await hass.services.async_call(
        DOMAIN,
        "record_run_event",
        {
            "profile_id": "p1",
            "run_id": "run-1",
            "started_at": "2024-01-01T00:00:00Z",
            "targets_met": 8,
            "targets_total": 10,
            "stress_events": 1,
        },
        blocking=True,
        return_response=True,
    )
    assert response["run_event"]["run_id"] == "run-1"
    success = response.get("success_statistics", {}).get("profile")
    assert success is not None
    assert success["stats_version"] == "success/v1"
    payload = success["payload"]
    assert payload["targets_total"] == pytest.approx(10.0)
    assert payload["targets_met"] == pytest.approx(8.0)
    assert payload["weighted_success_percent"] == pytest.approx(80.0)
    registry = hass.data[DOMAIN]["registry"]
    profile = registry.get("p1")
    assert profile is not None and len(profile.run_history) == 1


async def test_record_harvest_event_service_updates_statistics(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    await hass.services.async_call(
        DOMAIN,
        "record_run_event",
        {
            "profile_id": "p1",
            "run_id": "run-1",
            "started_at": "2024-01-01T00:00:00Z",
        },
        blocking=True,
    )
    response = await hass.services.async_call(
        DOMAIN,
        "record_harvest_event",
        {
            "profile_id": "p1",
            "harvest_id": "harvest-1",
            "harvested_at": "2024-02-01T00:00:00Z",
            "yield_grams": 42.5,
            "area_m2": 1.5,
        },
        blocking=True,
        return_response=True,
    )
    assert response["harvest_event"]["yield_grams"] == 42.5
    registry = hass.data[DOMAIN]["registry"]
    profile = registry.get("p1")
    assert profile and profile.statistics
    metrics = profile.statistics[0].metrics
    assert metrics["total_yield_grams"] == 42.5


async def test_record_harvest_event_service_rejects_invalid_payload(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            "record_harvest_event",
            {
                "profile_id": "p1",
                "harvest_id": "bad",
                "harvested_at": "2024-02-01T00:00:00Z",
                "yield_grams": -2,
            },
            blocking=True,
        )

    assert "yield_grams" in str(excinfo.value)


async def test_record_nutrient_event_service_updates_statistics(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    response = await hass.services.async_call(
        DOMAIN,
        "record_nutrient_event",
        {
            "profile_id": "p1",
            "event_id": "feed-1",
            "applied_at": "2024-03-01T08:00:00Z",
            "product_name": "Grow A",
            "solution_volume_liters": 9.5,
            "concentration_ppm": 700,
        },
        blocking=True,
        return_response=True,
    )

    event = response["nutrient_event"]
    assert event["product_name"] == "Grow A"
    stats = response.get("nutrient_statistics", {}).get("profile")
    assert stats is not None
    assert stats["stats_version"] == NUTRIENT_STATS_VERSION
    metrics = stats["payload"]["metrics"]
    assert metrics["total_events"] == pytest.approx(1.0)
    assert metrics["total_volume_liters"] == pytest.approx(9.5)

    registry = hass.data[DOMAIN]["registry"]
    profile = registry.get("p1")
    assert profile is not None and len(profile.nutrient_history) == 1


async def test_record_nutrient_event_service_rejects_invalid_payload(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            "record_nutrient_event",
            {
                "profile_id": "p1",
                "event_id": "feed-invalid",
                "applied_at": "2024-03-01T08:00:00Z",
                "ph": 15.5,
            },
            blocking=True,
        )

    assert "ph" in str(excinfo.value)


async def test_record_cultivation_event_service_returns_statistics(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    response = await hass.services.async_call(
        DOMAIN,
        "record_cultivation_event",
        {
            "profile_id": "p1",
            "event_id": "evt-1",
            "occurred_at": "2024-04-02T10:15:00Z",
            "event_type": "inspection",
            "notes": "No pests observed",
        },
        blocking=True,
        return_response=True,
    )

    event = response["cultivation_event"]
    assert event["event_type"] == "inspection"
    stats = response.get("event_statistics", {}).get("profile")
    assert stats is not None
    assert stats["stats_version"] == EVENT_STATS_VERSION
    metrics = stats["payload"]["metrics"]
    assert metrics["total_events"] == pytest.approx(1.0)

    registry = hass.data[DOMAIN]["registry"]
    profile = registry.get("p1")
    assert profile is not None and len(profile.event_history) == 1


async def test_record_cultivation_event_service_requires_event_type(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            "record_cultivation_event",
            {
                "profile_id": "p1",
                "event_id": "evt-invalid",
                "occurred_at": "2024-04-02T10:15:00Z",
                "event_type": "",
            },
            blocking=True,
        )

    assert "event_type" in str(excinfo.value)


async def test_profile_runs_service_returns_runs(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    await hass.services.async_call(
        DOMAIN,
        "record_run_event",
        {
            "profile_id": "p1",
            "run_id": "run-service",
            "started_at": "2024-01-02T00:00:00Z",
        },
        blocking=True,
    )
    response = await hass.services.async_call(
        DOMAIN,
        "profile_runs",
        {"profile_id": "p1"},
        blocking=True,
        return_response=True,
    )
    runs = response["runs"]
    assert response["profile_id"] == "p1"
    assert runs and runs[0]["run_id"] == "run-service"


async def test_profile_provenance_service_returns_counts(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    registry = hass.data[DOMAIN]["registry"]
    profile = registry.get("p1")
    assert profile is not None

    manual_annotation = FieldAnnotation(source_type="manual", method="manual")
    profile.resolved_targets["humidity_optimal"] = ResolvedTarget(
        value=60,
        annotation=manual_annotation,
        citations=[],
    )
    inherited_annotation = FieldAnnotation(
        source_type="inheritance",
        source_ref=["p1", "species"],
        method="inheritance",
        extras={
            "inheritance_depth": 1,
            "source_profile_id": "species",
            "source_profile_type": "species",
            "source_profile_name": "Species",
        },
    )
    profile.resolved_targets["temperature_optimal"] = ResolvedTarget(
        value=21.5,
        annotation=inherited_annotation,
        citations=[],
    )
    profile.last_resolved = "2024-01-01T00:00:00Z"
    profile.refresh_sections()

    response = await hass.services.async_call(
        DOMAIN,
        "profile_provenance",
        {"profile_id": "p1", "include_extras": True},
        blocking=True,
        return_response=True,
    )

    assert response["profile_id"] == "p1"
    counts = response["counts"]
    assert counts["total"] == 2
    assert counts["overrides"] == 1
    assert counts["inherited"] == 1
    assert response["badges"]["temperature_optimal"]["badge"] == "inherited"
    assert response["badge_counts"]["override"] == 1
    summary = response["summary"]
    assert summary["temperature_optimal"]["is_inherited"] is True
    assert summary["humidity_optimal"]["source_type"] == "manual"
    groups = response["groups"]
    assert "temperature_optimal" in groups["inherited"]
    assert "humidity_optimal" in groups["overrides"]


async def test_export_profiles_overwrites_existing(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    out = tmp_path / "profiles.json"
    out.write_text("[]")
    await hass.services.async_call(DOMAIN, "export_profiles", {"path": str(out)}, blocking=True)
    data = json.loads(out.read_text())
    assert len(data) == 1 and data[0]["plant_id"] == "p1"


async def test_export_profiles_invalid_path(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    bad = tmp_path / "dir" / ".." / "profiles.json"
    await hass.services.async_call(DOMAIN, "export_profiles", {"path": str(bad)}, blocking=True)
    assert bad.resolve().exists()


async def test_export_profile_creates_parent_dir(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    nested = tmp_path / "nested" / "p1.json"
    await hass.services.async_call(
        DOMAIN,
        "export_profile",
        {"profile_id": "p1", "path": str(nested)},
        blocking=True,
    )
    assert nested.exists()


async def test_export_profile_relative_path_uses_config(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    rel = "p1_rel.json"
    await hass.services.async_call(
        DOMAIN,
        "export_profile",
        {"profile_id": "p1", "path": rel},
        blocking=True,
    )
    assert Path(hass.config.path(rel)).exists()


async def test_replace_sensor_migrates_legacy_options(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"sensors": {"moisture": "sensor.old"}, "plant_id": "legacy"},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with (
        patch.object(hca, "HortiAICoordinator") as mock_ai,
        patch.object(hca, "HortiLocalCoordinator") as mock_local,
    ):
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)

    profiles = entry.options["profiles"]
    pid = next(iter(profiles))
    assert profiles[pid]["plant_id"] == pid

    reg = er.async_get(hass)
    reg.async_get_or_create("sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture")
    reg.async_get_or_create("sensor", "test", "sensor_new", suggested_object_id="new", original_device_class="moisture")
    hass.states.async_set("sensor.old", 1)
    hass.states.async_set("sensor.new", 2)
    await hass.services.async_call(
        DOMAIN,
        "replace_sensor",
        {"profile_id": pid, "measurement": "moisture", "entity_id": "sensor.new"},
        blocking=True,
    )
    assert entry.options["profiles"][pid]["sensors"]["moisture"] == "sensor.new"


async def test_refresh_species_multiple_profiles(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    entry.options["profiles"]["p2"] = {"name": "Plant 2"}
    hass.config_entries.async_update_entry(entry, options=entry.options)
    await hass.services.async_call(DOMAIN, "refresh_species", {"profile_id": "p2"}, blocking=True)
    from custom_components.horticulture_assistant.profile.store import async_get_profile

    prof = await async_get_profile(hass, "p2")
    assert prof["plant_id"] == "p2"


async def test_cloud_login_service_updates_tokens(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    manager = hass.data[DOMAIN][entry.entry_id]["cloud_sync_manager"]
    tokens = CloudAuthTokens(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_at=datetime(2025, 1, 1, tzinfo=UTC),
        tenant_id="tenant-1",
        device_token="device-1",
        account_email="user@example.com",
        roles=("grower",),
        organization_id="org-1",
        organization_name="Org One",
        organization_role="admin",
        organizations=(
            CloudOrganization(org_id="org-1", name="Org One", roles=("admin",), default=True),
            CloudOrganization(org_id="org-2", name="Org Two", roles=("viewer",)),
        ),
    )
    with (
        patch(
            "custom_components.horticulture_assistant.services.CloudAuthClient.async_login",
            AsyncMock(return_value=tokens),
        ),
        patch.object(manager, "async_refresh", AsyncMock()) as refresh,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            "cloud_login",
            {
                "base_url": "https://cloud.example",
                "email": "user@example.com",
                "password": "secret",
            },
            blocking=True,
            return_response=True,
        )
    assert entry.options[CONF_CLOUD_SYNC_ENABLED] is True
    assert entry.options[CONF_CLOUD_ACCESS_TOKEN] == "access-token"
    assert entry.options[CONF_CLOUD_REFRESH_TOKEN] == "refresh-token"
    assert entry.options[CONF_CLOUD_TENANT_ID] == "tenant-1"
    assert entry.options[CONF_CLOUD_DEVICE_TOKEN] == "device-1"
    assert entry.options[CONF_CLOUD_ACCOUNT_EMAIL] == "user@example.com"
    assert entry.options[CONF_CLOUD_ACCOUNT_ROLES] == ["grower"]
    assert entry.options[CONF_CLOUD_ORGANIZATION_ID] == "org-1"
    assert entry.options[CONF_CLOUD_ORGANIZATION_NAME] == "Org One"
    assert entry.options[CONF_CLOUD_ORGANIZATION_ROLE] == "admin"
    orgs = entry.options[CONF_CLOUD_AVAILABLE_ORGANIZATIONS]
    assert isinstance(orgs, list) and orgs[0]["id"] == "org-1"
    assert response["tenant_id"] == "tenant-1"
    assert response["organization_id"] == "org-1"
    refresh.assert_awaited()


async def test_cloud_logout_clears_tokens(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    manager = hass.data[DOMAIN][entry.entry_id]["cloud_sync_manager"]
    entry.options.update(
        {
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_ACCESS_TOKEN: "token",
            CONF_CLOUD_REFRESH_TOKEN: "refresh",
            CONF_CLOUD_DEVICE_TOKEN: "device",
            CONF_CLOUD_ACCOUNT_EMAIL: "user@example.com",
            CONF_CLOUD_ACCOUNT_ROLES: ["grower"],
            CONF_CLOUD_TOKEN_EXPIRES_AT: "2025-01-01T00:00:00Z",
            CONF_CLOUD_AVAILABLE_ORGANIZATIONS: [{"id": "org-1", "name": "Org One"}],
            CONF_CLOUD_ORGANIZATION_ID: "org-1",
            CONF_CLOUD_ORGANIZATION_NAME: "Org One",
            CONF_CLOUD_ORGANIZATION_ROLE: "admin",
        }
    )
    with patch.object(manager, "async_refresh", AsyncMock()) as refresh:
        await hass.services.async_call(
            DOMAIN,
            "cloud_logout",
            {},
            blocking=True,
        )
    assert entry.options.get(CONF_CLOUD_SYNC_ENABLED) is False
    assert CONF_CLOUD_ACCESS_TOKEN not in entry.options
    assert CONF_CLOUD_REFRESH_TOKEN not in entry.options
    assert CONF_CLOUD_AVAILABLE_ORGANIZATIONS not in entry.options
    assert CONF_CLOUD_ORGANIZATION_ID not in entry.options
    refresh.assert_awaited()


async def test_cloud_refresh_updates_expiry(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    manager = hass.data[DOMAIN][entry.entry_id]["cloud_sync_manager"]
    entry.options.update(
        {
            CONF_CLOUD_REFRESH_TOKEN: "refresh-token",
            CONF_CLOUD_BASE_URL: "https://cloud.example",
        }
    )
    tokens = CloudAuthTokens(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        tenant_id="tenant-1",
        device_token="device-2",
        account_email="user@example.com",
        roles=("grower", "admin"),
        organization_id="org-1",
        organization_name="Org One",
        organization_role="admin",
        organizations=(CloudOrganization(org_id="org-1", name="Org One", roles=("admin",), default=True),),
    )
    with (
        patch(
            "custom_components.horticulture_assistant.cloudsync.manager.CloudAuthClient.async_refresh",
            AsyncMock(return_value=tokens),
        ),
        patch.object(manager, "async_refresh", AsyncMock()) as refresh,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            "cloud_refresh_token",
            {},
            blocking=True,
            return_response=True,
        )
    assert entry.options[CONF_CLOUD_ACCESS_TOKEN] == "new-access"
    assert entry.options[CONF_CLOUD_REFRESH_TOKEN] == "new-refresh"
    assert entry.options[CONF_CLOUD_DEVICE_TOKEN] == "device-2"
    assert entry.options[CONF_CLOUD_ACCOUNT_ROLES] == ["grower", "admin"]
    assert entry.options[CONF_CLOUD_ORGANIZATION_ID] == "org-1"
    assert response["tenant_id"] == "tenant-1"
    assert response["organization_id"] == "org-1"
    assert response["token_expires_at"] == entry.options[CONF_CLOUD_TOKEN_EXPIRES_AT]
    refresh.assert_awaited()


async def test_cloud_select_org_updates_entry(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    manager = hass.data[DOMAIN][entry.entry_id]["cloud_sync_manager"]
    entry.options.update(
        {
            CONF_CLOUD_AVAILABLE_ORGANIZATIONS: [
                {"id": "org-1", "name": "Org One", "default": True, "roles": ["admin"]},
                {"id": "org-2", "name": "Org Two", "roles": ["viewer"]},
            ],
            CONF_CLOUD_ORGANIZATION_ID: "org-1",
            CONF_CLOUD_ORGANIZATION_NAME: "Org One",
            CONF_CLOUD_ORGANIZATION_ROLE: "admin",
        }
    )
    with patch.object(manager, "async_refresh", AsyncMock()) as refresh:
        response = await hass.services.async_call(
            DOMAIN,
            "cloud_select_org",
            {"organization_id": "org-2"},
            blocking=True,
            return_response=True,
        )
    assert entry.options[CONF_CLOUD_ORGANIZATION_ID] == "org-2"
    assert entry.options[CONF_CLOUD_ORGANIZATION_NAME] == "Org Two"
    assert entry.options[CONF_CLOUD_ORGANIZATION_ROLE] == "viewer"
    orgs = entry.options[CONF_CLOUD_AVAILABLE_ORGANIZATIONS]
    assert orgs[1]["default"] is True
    assert response["organization_id"] == "org-2"
    refresh.assert_awaited()


async def test_cloud_sync_now_service_calls_manager(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    manager = hass.data[DOMAIN][entry.entry_id]["cloud_sync_manager"]
    payload = {"pushed": 3, "pulled": 1, "status": {"manual_sync": {"result": {}}}}
    with patch.object(manager, "async_sync_now", AsyncMock(return_value=payload)) as sync:
        response = await hass.services.async_call(
            DOMAIN,
            "cloud_sync_now",
            {"push": False},
            blocking=True,
            return_response=True,
        )
    sync.assert_awaited_with(push=False, pull=True)
    assert response == payload


async def test_cloud_sync_now_service_raises_error(hass, tmp_path):
    entry = await _setup_entry_with_profile(hass, tmp_path)
    manager = hass.data[DOMAIN][entry.entry_id]["cloud_sync_manager"]
    with (
        patch.object(manager, "async_sync_now", AsyncMock(side_effect=CloudSyncError("boom"))),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "cloud_sync_now",
            {},
            blocking=True,
        )
