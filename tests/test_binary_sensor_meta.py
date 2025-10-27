import pytest

from custom_components.horticulture_assistant.binary_sensor import (
    FaultDetectionBinarySensor,
    IrrigationReadinessBinarySensor,
    SensorHealthBinarySensor,
)
from custom_components.horticulture_assistant.utils.entry_helpers import ProfileContext
from custom_components.horticulture_assistant.const import DOMAIN


@pytest.mark.asyncio
async def test_binary_sensor_unique_id_and_device_info(hass):
    context = ProfileContext(
        id="plant1",
        name="Plant",
        sensors={"temperature": ("sensor.temp",)},
    )
    sensor = SensorHealthBinarySensor(hass, "entry1", context)
    assert sensor.unique_id == f"{DOMAIN}_entry1_plant1_sensor_health"
    assert (DOMAIN, "entry1:profile:plant1") in sensor.device_info["identifiers"]


@pytest.mark.asyncio
async def test_sensor_health_uses_monitor(hass):
    context = ProfileContext(
        id="plant1",
        name="Plant",
        sensors={"moisture": ("sensor.plant1_moisture",)},
    )
    sensor = SensorHealthBinarySensor(hass, "entry1", context)

    await sensor.async_update()
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["issues"][0]["summary"] == "sensor_missing"

    hass.states.async_set("sensor.plant1_moisture", "45")
    await sensor.async_update()
    assert sensor.is_on is False


@pytest.mark.asyncio
async def test_fault_detection_respects_thresholds(hass):
    context = ProfileContext(
        id="plant1",
        name="Plant",
        sensors={"moisture": ("sensor.plant1_moisture",)},
        thresholds={"moisture_min": 30, "moisture_max": 70},
    )
    sensor = FaultDetectionBinarySensor(hass, "entry1", context)

    hass.states.async_set("sensor.plant1_moisture", "20")
    await sensor.async_update()
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["issues"][0]["summary"] == "sensor_below_minimum"

    hass.states.async_set("sensor.plant1_moisture", "50")
    await sensor.async_update()
    assert sensor.is_on is False


@pytest.mark.asyncio
async def test_irrigation_readiness_uses_profile_threshold(hass):
    context = ProfileContext(
        id="plant1",
        name="Plant",
        sensors={"moisture": ("sensor.plant1_moisture",)},
        thresholds={"moisture_min": 35},
    )
    sensor = IrrigationReadinessBinarySensor(hass, "entry1", context)

    hass.states.async_set("sensor.plant1_moisture", "60")
    await sensor.async_update()
    assert sensor.is_on is False

    hass.states.async_set("sensor.plant1_moisture", "30")
    await sensor.async_update()
    assert sensor.is_on is True
