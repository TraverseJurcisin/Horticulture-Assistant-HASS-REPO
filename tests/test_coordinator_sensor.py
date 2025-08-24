import importlib
import pathlib
import sys
import types

import pytest

# Bypass the package __init__ which pulls in Home Assistant by creating a minimal
# module placeholder with an explicit path for submodule resolution.
pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [
    str(
        pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant"
    )
]
sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

const = importlib.import_module("custom_components.horticulture_assistant.const")
coordinator_mod = importlib.import_module("custom_components.horticulture_assistant.coordinator")
entity_mod = importlib.import_module("custom_components.horticulture_assistant.entity")
sensor_mod = importlib.import_module("custom_components.horticulture_assistant.sensor")

CONF_PROFILES = const.CONF_PROFILES
HorticultureCoordinator = coordinator_mod.HorticultureCoordinator
HorticultureBaseEntity = entity_mod.HorticultureBaseEntity
ProfileDLISensor = sensor_mod.ProfileDLISensor


@pytest.mark.asyncio
async def test_coordinator_returns_profile_data(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()

    assert "profiles" in coordinator.data
    assert "avocado" in coordinator.data["profiles"]
    prof = coordinator.data["profiles"]["avocado"]
    assert prof["name"] == "Avocado"
    assert prof["metrics"]["dli"] is None


@pytest.mark.asyncio
async def test_base_entity_device_info(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()

    entity = HorticultureBaseEntity(coordinator, "avocado", "Avocado")
    info = entity.device_info
    assert info["name"] == "Avocado"
    assert info["identifiers"] == {("horticulture_assistant", "profile:avocado")}


@pytest.mark.asyncio
async def test_dli_sensor_reads_illuminance(hass):
    hass.states.async_set("sensor.light", 2000)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"illuminance": "sensor.light"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()

    sensor = ProfileDLISensor(coordinator, "avocado", "Avocado")
    assert sensor.native_value == pytest.approx(0.02)
