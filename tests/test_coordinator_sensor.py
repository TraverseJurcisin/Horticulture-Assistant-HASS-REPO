import importlib
import logging
import pathlib
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

# Bypass the package __init__ which pulls in Home Assistant by creating a minimal
# module placeholder with an explicit path for submodule resolution.
pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [str(pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")]
sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

const = importlib.import_module("custom_components.horticulture_assistant.const")
coordinator_mod = importlib.import_module("custom_components.horticulture_assistant.coordinator")
entity_mod = importlib.import_module("custom_components.horticulture_assistant.entity")
sensor_mod = importlib.import_module("custom_components.horticulture_assistant.sensor")

CONF_PROFILES = const.CONF_PROFILES
HorticultureCoordinator = coordinator_mod.HorticultureCoordinator
HorticultureEntity = entity_mod.HorticultureEntity
ProfileMetricSensor = sensor_mod.ProfileMetricSensor
PROFILE_SENSOR_DESCRIPTIONS = sensor_mod.PROFILE_SENSOR_DESCRIPTIONS


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
    assert "mold_risk" in prof["metrics"]


@pytest.mark.asyncio
async def test_coordinator_honors_update_interval(hass):
    options = {CONF_PROFILES: {}, "update_interval": 10}
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    assert coordinator.update_interval.total_seconds() == 600


@pytest.mark.asyncio
async def test_base_entity_device_info(hass):
    options = {CONF_PROFILES: {"avocado": {"name": "Avocado"}}}
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()

    entity = HorticultureEntity(coordinator, "avocado", "Avocado")
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

    ppfd_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["ppfd"])
    dli_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dli"])
    # 2000 lux -> 37 PPFD; over a 5-minute interval yields ~0.011 mol/m²·day
    assert ppfd_sensor.native_value == pytest.approx(37.0, rel=1e-2)
    assert dli_sensor.native_value == pytest.approx(0.011, rel=1e-2)


@pytest.mark.asyncio
async def test_dli_accumulates_over_updates(hass):
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
    await coordinator.async_request_refresh()

    dli_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dli"])
    assert dli_sensor.native_value == pytest.approx(0.022, rel=1e-2)


@pytest.mark.asyncio
async def test_dli_resets_daily(hass):
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
    start = datetime(2024, 1, 1, tzinfo=dt_util.UTC)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start,
    ):
        await coordinator.async_config_entry_first_refresh()
    dli_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dli"])
    assert dli_sensor.native_value == pytest.approx(0.011, rel=1e-2)
    with patch(
        "custom_components.horticulture_assistant.coordinator.dt_util.utcnow",
        return_value=start + timedelta(days=1),
    ):
        await coordinator.async_request_refresh()
    assert dli_sensor.native_value == pytest.approx(0.011, rel=1e-2)


@pytest.mark.asyncio
async def test_profile_vpd_and_dew_point_sensors(hass):
    hass.states.async_set("sensor.t", 25)
    hass.states.async_set("sensor.h", 60)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"temperature": "sensor.t", "humidity": "sensor.h"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()

    vpd_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["vpd"])
    dew_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["dew_point"])
    assert vpd_sensor.native_value == pytest.approx(1.27, rel=1e-2)
    assert dew_sensor.native_value == pytest.approx(16.7, rel=1e-2)
    assert coordinator.data["profiles"]["avocado"]["metrics"]["mold_risk"] == 0.0


@pytest.mark.asyncio
async def test_profile_moisture_sensor(hass):
    hass.states.async_set("sensor.m", 55)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {"moisture": "sensor.m"},
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()

    moisture_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["moisture"])
    assert moisture_sensor.native_value == 55


@pytest.mark.asyncio
async def test_profile_status_sensor(hass):
    hass.states.async_set("sensor.m", 5)
    hass.states.async_set("sensor.t", 25)
    hass.states.async_set("sensor.h", 95)
    options = {
        CONF_PROFILES: {
            "avocado": {
                "name": "Avocado",
                "sensors": {
                    "moisture": "sensor.m",
                    "temperature": "sensor.t",
                    "humidity": "sensor.h",
                },
            }
        }
    }
    coordinator = HorticultureCoordinator(hass, "entry1", options)
    await coordinator.async_config_entry_first_refresh()
    status_sensor = ProfileMetricSensor(coordinator, "avocado", "Avocado", PROFILE_SENSOR_DESCRIPTIONS["status"])
    assert status_sensor.native_value == "critical"


@pytest.mark.asyncio
async def test_status_and_recommendation_device_info(hass):
    async def _async_update():
        return {}

    ai = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="ai", update_method=_async_update)
    local = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="local", update_method=_async_update)
    status = sensor_mod.HortiStatusSensor(ai, local, "entry1", "Plant", "pid", True)
    rec = sensor_mod.HortiRecommendationSensor(ai, "entry1", "Plant", "pid", True)
    info = status.device_info
    assert info["identifiers"] == {("horticulture_assistant", "plant:pid")}
    assert info["name"] == "Plant"
    assert rec.device_info == info
