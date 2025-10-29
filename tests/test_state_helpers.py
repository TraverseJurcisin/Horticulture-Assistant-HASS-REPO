import importlib.util
import sys
import types
from pathlib import Path

import pytest

from custom_components.horticulture_assistant.utils import state_helpers

pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant")]
sys.modules.setdefault("custom_components.horticulture_assistant", pkg)

spec = importlib.util.spec_from_file_location(
    "custom_components.horticulture_assistant.coordinator",
    Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant" / "coordinator.py",
)
coordinator_mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(coordinator_mod)
HorticultureCoordinator = coordinator_mod.HorticultureCoordinator
UnitOfTemperature = coordinator_mod.UnitOfTemperature
TemperatureConverter = coordinator_mod.TemperatureConverter


def test_state_helpers_import_and_get_numeric_state():
    hass = types.SimpleNamespace(
        states=types.SimpleNamespace(get=lambda entity_id: types.SimpleNamespace(state="12.5"))
    )

    value = state_helpers.get_numeric_state(hass, "sensor.example")
    assert value == 12.5


def test_parse_entities_ignores_none_and_blank_entries():
    """None values or blank strings should be removed when parsing entities."""

    entities = state_helpers.parse_entities([None, "  ", "sensor.one", "sensor.one", "", None])

    assert entities == ["sensor.one"]


def test_parse_entities_handles_mixed_iterables():
    """Non-string iterable members should be coerced while ignoring falsy items."""

    entities = state_helpers.parse_entities(["sensor.one", Path("sensor.two"), None, ""])

    assert entities == ["sensor.one", "sensor.two"]


@pytest.mark.asyncio
async def test_coordinator_converts_fahrenheit_to_celsius(hass, monkeypatch):
    """Fahrenheit temperature states should be converted before computing metrics."""

    def fake_convert(value, from_unit, to_unit):
        if from_unit == UnitOfTemperature.FAHRENHEIT and to_unit == UnitOfTemperature.CELSIUS:
            return (float(value) - 32.0) * 5.0 / 9.0
        return value

    monkeypatch.setattr(TemperatureConverter, "convert", staticmethod(fake_convert))

    entry = types.SimpleNamespace(entry_id="entry", options={}, data={})
    coordinator = HorticultureCoordinator(hass, entry)

    hass.states.async_set("sensor.temp_f", "77", {"unit_of_measurement": "F"})
    hass.states.async_set("sensor.humidity", "60")

    metrics = await coordinator._compute_metrics(
        "plant1",
        {
            "sensors": {
                "temperature": "sensor.temp_f",
                "humidity": "sensor.humidity",
            }
        },
    )

    assert metrics["dew_point"] == pytest.approx(16.7, rel=1e-2)
    assert metrics["vpd"] == pytest.approx(1.27, rel=1e-2)
