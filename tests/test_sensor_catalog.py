from enum import Enum

import pytest

from custom_components.horticulture_assistant import sensor_catalog
from custom_components.horticulture_assistant.sensor_catalog import (
    collect_sensor_suggestions,
    format_sensor_hints,
)

pytestmark = pytest.mark.asyncio


async def test_collect_sensor_suggestions_prioritises_device_class(hass):
    hass.states.async_set(
        "sensor.soil_moisture",
        42,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )
    hass.states.async_set(
        "sensor.moisture_guess",
        21,
        {"device_class": "moisture", "unit_of_measurement": "ppm"},
    )
    hass.states.async_set("sensor.random", 5, {})

    suggestions = collect_sensor_suggestions(hass, ["moisture"])
    assert suggestions["moisture"]
    top = suggestions["moisture"][0]
    assert top.entity_id == "sensor.soil_moisture"
    assert top.score > suggestions["moisture"][1].score


async def test_format_sensor_hints_handles_missing_roles(hass):
    hints = format_sensor_hints({"moisture": []})
    assert "No matching sensors" in hints

    hass.states.async_set(
        "sensor.grow_temp",
        18,
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )
    suggestions = collect_sensor_suggestions(hass, ["temperature"])
    hints = format_sensor_hints({"temperature": suggestions["temperature"]})
    assert "sensor.grow_temp" in hints


async def test_collect_sensor_suggestions_handles_enum_units(hass, monkeypatch):
    class FakeTemperatureUnit(Enum):
        CELSIUS = "°C"

    hass.states.async_set(
        "sensor.enum_temp",
        19,
        {
            "device_class": "temperature",
            "unit_of_measurement": FakeTemperatureUnit.CELSIUS,
        },
    )

    monkeypatch.setitem(sensor_catalog.EXPECTED_UNITS, "temperature", {FakeTemperatureUnit.CELSIUS})

    suggestions = collect_sensor_suggestions(hass, ["temperature"])

    assert suggestions["temperature"]
    assert suggestions["temperature"][0].entity_id == "sensor.enum_temp"
