import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import CONF_API_KEY, DOMAIN
from custom_components.horticulture_assistant.services import er

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
    reg.async_get_or_create(
        "sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture"
    )
    reg.async_get_or_create(
        "sensor", "test", "sensor_good", suggested_object_id="good", original_device_class="moisture"
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
    registry = hass.data[DOMAIN]["profile_registry"]
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
    await hass.services.async_call(
        DOMAIN, "refresh_species", {"profile_id": "p1"}, blocking=True
    )
    from custom_components.horticulture_assistant.profile.store import async_get_profile

    prof = await async_get_profile(hass, "p1")
    assert prof["last_resolved"] == "1970-01-01T00:00:00Z"
    assert entry.options["profiles"]["p1"]["name"] == "Plant 1"


async def test_export_profiles_service_writes_file(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    out = tmp_path / "profiles.json"
    await hass.services.async_call(
        DOMAIN, "export_profiles", {"path": str(out)}, blocking=True
    )
    data = json.loads(out.read_text())
    assert data[0]["plant_id"] == "p1"


async def test_export_profiles_relative_path_uses_config(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    rel = "profiles_rel.json"
    await hass.services.async_call(
        DOMAIN, "export_profiles", {"path": rel}, blocking=True
    )
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
    reg.async_get_or_create(
        "sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture"
    )
    reg.async_get_or_create(
        "sensor", "test", "sensor_temp", suggested_object_id="temp", original_device_class="temperature"
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
        await hass.services.async_call(
            DOMAIN, "refresh_species", {"profile_id": "unknown"}, blocking=True
        )


async def test_export_profiles_creates_parent_dir(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    nested = tmp_path / "nested" / "profiles.json"
    await hass.services.async_call(
        DOMAIN, "export_profiles", {"path": str(nested)}, blocking=True
    )
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
    await hass.services.async_call(
        DOMAIN, "refresh_species", {"profile_id": "p1"}, blocking=True
    )
    store_file = Path(hass.config.path("horticulture_assistant/profiles/p1.json"))
    assert store_file.exists()
    data = json.loads(store_file.read_text())
    assert data["plant_id"] == "p1"


async def test_export_profiles_overwrites_existing(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    out = tmp_path / "profiles.json"
    out.write_text("[]")
    await hass.services.async_call(
        DOMAIN, "export_profiles", {"path": str(out)}, blocking=True
    )
    data = json.loads(out.read_text())
    assert len(data) == 1 and data[0]["plant_id"] == "p1"


async def test_export_profiles_invalid_path(hass, tmp_path):
    await _setup_entry_with_profile(hass, tmp_path)
    bad = tmp_path / "dir" / ".." / "profiles.json"
    await hass.services.async_call(
        DOMAIN, "export_profiles", {"path": str(bad)}, blocking=True
    )
    assert bad.resolve().exists()


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

    reg = er.async_get(hass)
    reg.async_get_or_create(
        "sensor", "test", "sensor_old", suggested_object_id="old", original_device_class="moisture"
    )
    reg.async_get_or_create(
        "sensor", "test", "sensor_new", suggested_object_id="new", original_device_class="moisture"
    )
    hass.states.async_set("sensor.old", 1)
    hass.states.async_set("sensor.new", 2)
    pid = next(iter(entry.options["profiles"].keys()))
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
    await hass.services.async_call(
        DOMAIN, "refresh_species", {"profile_id": "p2"}, blocking=True
    )
    from custom_components.horticulture_assistant.profile.store import async_get_profile

    prof = await async_get_profile(hass, "p2")
    assert prof["plant_id"] == "p2"
