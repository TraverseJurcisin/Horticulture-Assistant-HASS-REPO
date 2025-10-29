import pytest

from custom_components.horticulture_assistant.const import EVENT_YIELD_UPDATE
from custom_components.horticulture_assistant.utils.yield_tracker import YieldTracker


class _DummyBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def fire(self, event: str, data: dict) -> None:
        self.events.append((event, data))


class _DummyConfig:
    def __init__(self, base):
        self._base = base

    def path(self, *parts: str) -> str:
        return str(self._base.joinpath(*parts))


class _DummyHass:
    def __init__(self, base):
        self.config = _DummyConfig(base)
        self.bus = _DummyBus()


def test_add_entry_emits_yield_update(tmp_path):
    hass = _DummyHass(tmp_path)
    tracker = YieldTracker(data_file=str(tmp_path / "yield_logs.json"), hass=hass)

    tracker.add_entry("plant1", 42)

    assert hass.bus.events, "Expected yield update event to be fired"
    event, payload = hass.bus.events[0]
    assert event == EVENT_YIELD_UPDATE
    assert payload["plant_id"] == "plant1"
    assert payload["yield"] == pytest.approx(42.0)
