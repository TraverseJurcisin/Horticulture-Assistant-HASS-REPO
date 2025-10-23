import importlib
import json
import pathlib
import sys
import types
from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from homeassistant import exceptions

try:
    from pytest_homeassistant_custom_component.common import MockConfigEntry
except Exception:  # pragma: no cover
    MockConfigEntry = None

if MockConfigEntry is None:
    # Create a minimal package placeholder so service modules import even when
    # the Home Assistant test harness isn't available. When the plugin is
    # present, tests import the real integration instead.
    pkg = types.ModuleType("custom_components.horticulture_assistant")
    pkg.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")]
    sys.modules.setdefault("custom_components.horticulture_assistant", pkg)
    comps = types.ModuleType("homeassistant.components")
    sensor = types.ModuleType("homeassistant.components.sensor")

    class SensorDeviceClass:  # pragma: no cover - minimal enum
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ILLUMINANCE = "illuminance"
        MOISTURE = "moisture"
        CO2 = "co2"
        PH = "ph"

    sensor.SensorDeviceClass = SensorDeviceClass
    sys.modules.setdefault("homeassistant.components", comps)
    sys.modules.setdefault("homeassistant.components.sensor", sensor)
    sys.modules.setdefault("homeassistant.helpers.entity_registry", types.ModuleType("entity_registry"))
else:  # pragma: no cover - exercised only when plugin installed
    import custom_components.horticulture_assistant  # noqa: F401

services = importlib.import_module("custom_components.horticulture_assistant.services")
const = importlib.import_module("custom_components.horticulture_assistant.const")
CONF_API_KEY = const.CONF_API_KEY
CONF_CLOUD_FEATURE_FLAGS = const.CONF_CLOUD_FEATURE_FLAGS
DOMAIN = const.DOMAIN
FEATURE_AI_ASSIST = const.FEATURE_AI_ASSIST
FEATURE_IRRIGATION_AUTOMATION = const.FEATURE_IRRIGATION_AUTOMATION

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
    pytest.mark.skipif(MockConfigEntry is None, reason="pytest-homeassistant-custom-component not installed"),
]


class _DummyRegistry:
    def __init__(self):
        self._entries = {}

    def async_get_or_create(self, _domain, _platform, _unique_id, suggested_object_id=None, original_device_class=None):
        eid = suggested_object_id or _unique_id
        entry = types.SimpleNamespace(device_class=original_device_class, original_device_class=original_device_class)
        self._entries[eid] = entry
        return entry

    def async_get(self, entity_id):
        key = entity_id.split(".")[-1]
        return self._entries.get(key)


@pytest.fixture(autouse=True)
def dummy_entity_registry(monkeypatch):
    reg = _DummyRegistry()
    monkeypatch.setattr(services.er, "async_get", lambda hass: reg)
    return reg


@pytest.fixture(autouse=True)
def patch_coordinators():
    import custom_components.horticulture_assistant as hca

    hca.PLATFORMS = []
    with (
        patch.object(hca, "HortiAICoordinator") as mock_ai,
        patch.object(hca, "HortiLocalCoordinator") as mock_local,
    ):
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        yield


async def test_replace_sensor_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="Plant 1",
        options={"profiles": {"plant1": {"name": "Plant 1", "sensors": {"moisture": "sensor.old"}}}},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    reg = services.er.async_get(hass)
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
        {
            "profile_id": "plant1",
            "measurement": "moisture",
            "entity_id": "sensor.good",
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert entry.options["profiles"]["plant1"]["sensors"]["moisture"] == "sensor.good"


async def test_replace_sensor_service_device_class_mismatch(hass):
    """Replacement must match the expected device class."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="Plant 1",
        options={"profiles": {"plant1": {"name": "Plant 1", "sensors": {"moisture": "sensor.old"}}}},
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

    reg = services.er.async_get(hass)
    reg.async_get_or_create(
        "sensor",
        "test",
        "sensor_old",
        suggested_object_id="old",
        original_device_class="moisture",
    )
    # Register a candidate sensor with an incompatible device class
    reg.async_get_or_create(
        "sensor",
        "test",
        "sensor_bad",
        suggested_object_id="bad",
        original_device_class="humidity",
    )

    hass.states.async_set("sensor.old", 1)
    hass.states.async_set("sensor.bad", 2)
    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "replace_sensor",
            {
                "profile_id": "plant1",
                "measurement": "moisture",
                "entity_id": "sensor.bad",
            },
            blocking=True,
        )


async def test_refresh_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]
    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)
    local.async_request_refresh = AsyncMock(wraps=local.async_request_refresh)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "refresh", {"bad": 1}, blocking=True)
    await hass.services.async_call(DOMAIN, "refresh", {}, blocking=True)
    assert ai.async_request_refresh.called
    assert local.async_request_refresh.called


async def test_recalculate_and_run_recommendation_services(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            CONF_CLOUD_FEATURE_FLAGS: [FEATURE_AI_ASSIST, FEATURE_IRRIGATION_AUTOMATION],
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    store = hass.data[DOMAIN][entry.entry_id]["store"]
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]
    local = hass.data[DOMAIN][entry.entry_id]["coordinator_local"]

    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(DOMAIN, "recalculate_targets", {"plant_id": "p1"}, blocking=True)

    store.data.setdefault("plants", {})["p1"] = {}
    local.async_request_refresh = AsyncMock(wraps=local.async_request_refresh)
    await hass.services.async_call(DOMAIN, "recalculate_targets", {"plant_id": "p1"}, blocking=True)
    assert local.async_request_refresh.called

    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)
    ai.data = {"recommendation": "water"}
    await hass.services.async_call(
        DOMAIN,
        "run_recommendation",
        {"plant_id": "p1", "approve": True},
        blocking=True,
    )
    assert ai.async_request_refresh.called
    assert store.data["plants"]["p1"]["recommendation"] == "water"


async def test_run_recommendation_handles_missing_data(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={CONF_CLOUD_FEATURE_FLAGS: [FEATURE_AI_ASSIST]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]["store"]
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]

    store.data.setdefault("plants", {})["p1"] = {}
    ai.data = None
    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)

    await hass.services.async_call(
        DOMAIN,
        "run_recommendation",
        {"plant_id": "p1", "approve": True},
        blocking=True,
    )

    assert ai.async_request_refresh.called
    assert "recommendation" in store.data["plants"]["p1"]
    assert store.data["plants"]["p1"]["recommendation"] is None


async def test_run_recommendation_missing_data_preserves_existing(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={CONF_CLOUD_FEATURE_FLAGS: [FEATURE_AI_ASSIST]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]["store"]
    ai = hass.data[DOMAIN][entry.entry_id]["coordinator_ai"]

    plant = store.data.setdefault("plants", {}).setdefault("p1", {})
    plant["recommendation"] = "keep"
    ai.data = None
    ai.async_request_refresh = AsyncMock(wraps=ai.async_request_refresh)

    await hass.services.async_call(
        DOMAIN,
        "run_recommendation",
        {"plant_id": "p1", "approve": True},
        blocking=True,
    )

    assert ai.async_request_refresh.called
    assert store.data["plants"]["p1"]["recommendation"] == "keep"


async def test_run_recommendation_requires_entitlement(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    store = hass.data[DOMAIN][entry.entry_id]["store"]
    store.data.setdefault("plants", {})["p1"] = {}

    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "run_recommendation",
            {"plant_id": "p1", "approve": True},
            blocking=True,
        )


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_recompute_service(hass, expected_lingering_timers):
    """Ensure recompute service validates profile id and triggers refresh."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
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
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock(wraps=coord.async_request_refresh)
    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(DOMAIN, "recompute", {"profile_id": "bad"}, blocking=True)
    await hass.services.async_call(DOMAIN, "recompute", {"profile_id": "p1"}, blocking=True)
    await hass.services.async_call(DOMAIN, "recompute", {}, blocking=True)
    assert coord.async_request_refresh.call_count == 2


async def test_reset_dli_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant"}, "p2": {"name": "Two"}}},
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

    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord._dli_totals = {"p1": 1.2, "p2": 3.4}

    await hass.services.async_call(DOMAIN, "reset_dli", {"profile_id": "p1"}, blocking=True)
    assert "p1" not in coord._dli_totals and "p2" in coord._dli_totals

    await hass.services.async_call(DOMAIN, "reset_dli", {}, blocking=True)
    assert coord._dli_totals == {}


async def test_create_profile_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
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
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    await hass.services.async_call(DOMAIN, "create_profile", {"name": "Avocado"}, blocking=True)
    assert coord.async_request_refresh.called
    profiles = entry.options.get("profiles", {})
    assert any(p.get("name") == "Avocado" for p in profiles.values())


async def test_duplicate_profile_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            "profiles": {
                "p1": {
                    "name": "Plant 1",
                    "sensors": {"temperature": "sensor.temp"},
                    "thresholds": {"temp_min": 1},
                }
            }
        },
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
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        "duplicate_profile",
        {"source_profile_id": "p1", "new_name": "Copy"},
        blocking=True,
    )
    assert coord.async_request_refresh.called
    profiles = entry.options["profiles"]
    assert any(p.get("name") == "Copy" for p in profiles.values())
    new_id = next(pid for pid, p in profiles.items() if p["name"] == "Copy")
    assert profiles[new_id]["sensors"] == {"temperature": "sensor.temp"}
    assert profiles[new_id]["thresholds"] == {"temp_min": 1}
    assert profiles[new_id]["resolved_targets"]["temp_min"]["value"] == 1

    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "duplicate_profile",
            {"source_profile_id": "bad", "new_name": "x"},
            blocking=True,
        )


async def test_delete_profile_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca
    from custom_components.horticulture_assistant.profile.store import (
        async_get_profile,
        async_save_profile,
    )

    hca.PLATFORMS = []
    with (
        patch.object(hca, "HortiAICoordinator") as mock_ai,
        patch.object(hca, "HortiLocalCoordinator") as mock_local,
    ):
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
    await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    await async_save_profile(hass, {"plant_id": "p1", "display_name": "Plant 1"})
    assert await async_get_profile(hass, "p1") is not None

    await hass.services.async_call(DOMAIN, "delete_profile", {"profile_id": "p1"}, blocking=True)
    assert coord.async_request_refresh.called
    assert "p1" not in entry.options.get("profiles", {})
    assert await async_get_profile(hass, "p1") is None

    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(DOMAIN, "delete_profile", {"profile_id": "p1"}, blocking=True)


async def test_update_sensors_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
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
    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coord.async_request_refresh = AsyncMock()

    hass.states.async_set("sensor.temp", 10)
    await hass.services.async_call(
        DOMAIN,
        "update_sensors",
        {"profile_id": "p1", "temperature": "sensor.temp"},
        blocking=True,
    )
    assert coord.async_request_refresh.called
    assert entry.options["profiles"]["p1"]["sensors"] == {"temperature": "sensor.temp"}
    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "update_sensors",
            {"profile_id": "bad", "temperature": "sensor.temp"},
            blocking=True,
        )
    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "update_sensors",
            {"profile_id": "p1", "temperature": "sensor.miss"},
            blocking=True,
        )


async def test_update_sensors_service_merges_existing(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            "profiles": {
                "p1": {
                    "name": "Plant 1",
                    "sensors": {
                        "temperature": "sensor.old_temp",
                        "humidity": "sensor.humidity",
                    },
                }
            }
        },
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

    hass.states.async_set("sensor.humidity", 50)
    hass.states.async_set("sensor.new_temp", 22)

    await hass.services.async_call(
        DOMAIN,
        "update_sensors",
        {"profile_id": "p1", "temperature": "sensor.new_temp"},
        blocking=True,
    )

    sensors = entry.options["profiles"]["p1"]["sensors"]
    assert sensors == {"temperature": "sensor.new_temp", "humidity": "sensor.humidity"}

    registry = hass.data[DOMAIN]["registry"]
    profile = registry.get_profile("p1")
    assert profile is not None
    assert profile.general.get("sensors", {}) == sensors


async def test_export_profiles_service(hass, tmp_path):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
    )
    entry.add_to_hass(hass)
    import custom_components.horticulture_assistant as hca
    from custom_components.horticulture_assistant.profile.schema import BioProfile

    hca.PLATFORMS = []
    with (
        patch.object(hca, "HortiAICoordinator") as mock_ai,
        patch.object(hca, "HortiLocalCoordinator") as mock_local,
    ):
        mock_ai.return_value.async_config_entry_first_refresh = AsyncMock()
        mock_local.return_value.async_config_entry_first_refresh = AsyncMock()
        await hca.async_setup_entry(hass, entry)
    await hass.async_block_till_done()

    registry = hass.data[DOMAIN]["registry"]
    registry._profiles["p2"] = BioProfile(profile_id="p2", display_name="Plant 2")

    out = tmp_path / "profiles.json"
    await hass.services.async_call(DOMAIN, "export_profiles", {"path": str(out)}, blocking=True)

    data = json.loads(out.read_text())
    ids = {p["plant_id"] for p in data}
    assert ids == {"p1", "p2"}


async def test_export_profile_service(hass, tmp_path):
    """Ensure the export_profile service writes a single profile."""
    hass.config.path = lambda *p: str(tmp_path.joinpath(*p))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"profiles": {"p1": {"name": "Plant 1"}}},
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

    async def fake_get_profile(_hass, pid):
        if pid == "p1":
            return {
                "plant_id": "p1",
                "display_name": "Plant 1",
                "resolved_targets": {},
            }
        return None

    with patch(
        "custom_components.horticulture_assistant.profile.export.async_get_profile",
        side_effect=fake_get_profile,
    ):
        await hass.services.async_call(
            DOMAIN,
            "export_profile",
            {"profile_id": "p1", "path": "one.json"},
            blocking=True,
        )
        data = json.loads((tmp_path / "one.json").read_text())
        assert data["plant_id"] == "p1"
    with pytest.raises(exceptions.HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "export_profile",
            {"profile_id": "bad", "path": "bad.json"},
            blocking=True,
        )


async def test_import_profiles_service(hass, tmp_path):
    hass.config.path = lambda *p: str(tmp_path.joinpath(*p))
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
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

    registry = hass.data[DOMAIN]["registry"]
    assert registry.get("p1") is None

    profiles = {
        "p1": {
            "plant_id": "p1",
            "display_name": "Plant 1",
            "resolved_targets": {},
        }
    }
    (tmp_path / "profiles.json").write_text(json.dumps(profiles))

    await hass.services.async_call(DOMAIN, "import_profiles", {"path": "profiles.json"}, blocking=True)

    prof = registry.get("p1")
    assert prof is not None
    assert prof.display_name == "Plant 1"


async def test_clear_caches_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"})
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

    from custom_components.horticulture_assistant.ai_client import (
        _AI_CACHE,
        async_recommend_variable,
    )
    from custom_components.horticulture_assistant.opb_client import (
        _SPECIES_CACHE,
        async_fetch_field,
    )

    _AI_CACHE.clear()
    _SPECIES_CACHE.clear()

    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        AsyncMock(return_value=(1.0, 0.5, "s", [])),
    ):
        await async_recommend_variable(hass, "t", "p1")
    with patch(
        "custom_components.horticulture_assistant.opb_client.OpenPlantbookClient.species_details",
        AsyncMock(return_value={"t": {"min": 1}}),
    ):
        await async_fetch_field(hass, "slug", "t.min")

    assert _AI_CACHE and _SPECIES_CACHE

    await hass.services.async_call(DOMAIN, "clear_caches", {}, blocking=True)

    assert not _AI_CACHE
    assert not _SPECIES_CACHE


async def test_resolve_profile_persists_to_store(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            "profiles": {
                "p1": {
                    "name": "Plant 1",
                    "sources": {"temp_c_min": {"mode": "manual", "value": 10}},
                    "thresholds": {},
                    "citations": {},
                }
            }
        },
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

    await hass.services.async_call(DOMAIN, "resolve_profile", {"profile_id": "p1"}, blocking=True)
    from custom_components.horticulture_assistant.profile.store import (
        async_get_profile,
    )

    prof = await async_get_profile(hass, "p1")
    target = prof["resolved_targets"]["temp_c_min"]
    assert target["value"] == 10
    assert target["citations"][0]["source"] == "manual"


async def test_resolve_all_persists_every_profile(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            "profiles": {
                "p1": {
                    "name": "P1",
                    "sources": {"temp_c_min": {"mode": "manual", "value": 5}},
                    "thresholds": {},
                    "citations": {},
                },
                "p2": {
                    "name": "P2",
                    "sources": {"temp_c_min": {"mode": "manual", "value": 7}},
                    "thresholds": {},
                    "citations": {},
                },
            }
        },
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

    await hass.services.async_call(DOMAIN, "resolve_all", {}, blocking=True)
    from custom_components.horticulture_assistant.profile.store import (
        async_get_profile,
    )

    prof1 = await async_get_profile(hass, "p1")
    prof2 = await async_get_profile(hass, "p2")
    assert prof1["resolved_targets"]["temp_c_min"]["value"] == 5
    assert prof2["resolved_targets"]["temp_c_min"]["value"] == 7


async def test_recommend_watering_service(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={
            CONF_CLOUD_FEATURE_FLAGS: [FEATURE_IRRIGATION_AUTOMATION],
            "profiles": {
                "p1": {
                    "name": "Plant 1",
                    "sensors": {"moisture": "sensor.moist", "illuminance": "sensor.light"},
                }
            },
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.moist", 15)
    hass.states.async_set("sensor.light", 0)
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

    coord = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coord.async_request_refresh()

    result = await hass.services.async_call(
        DOMAIN,
        "recommend_watering",
        {"profile_id": "p1"},
        blocking=True,
        return_response=True,
    )
    assert result["minutes"] >= 10
