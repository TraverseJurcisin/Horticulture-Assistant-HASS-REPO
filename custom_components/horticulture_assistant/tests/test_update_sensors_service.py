import json
import asyncio
from pathlib import Path
from custom_components.horticulture_assistant.__init__ import update_sensors_service

class DummyConfig:
    def __init__(self, base: Path):
        self._base = base
    def path(self, name: str) -> str:
        return str(self._base / name)

class DummyHass:
    def __init__(self, base: Path):
        self.config = DummyConfig(base)


class DummyCall:
    def __init__(self, **data):
        self.data = data


def test_update_service(tmp_path: Path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {"sensor_entities": {"moisture_sensors": ["old"]}}
    (plants / "p1.json").write_text(json.dumps(profile))

    hass = DummyHass(tmp_path)
    call = DummyCall(plant_id="p1", sensors={"moisture_sensors": ["new"]})

    asyncio.run(update_sensors_service(hass, call))

    updated = json.load(open(plants / "p1.json", "r", encoding="utf-8"))
    sensors = updated.get("general", {}).get("sensor_entities", {})
    assert sensors["moisture_sensors"] == ["new"]


def test_update_service_invalid_data(tmp_path: Path):
    hass = DummyHass(tmp_path)
    call = DummyCall()

    # Should not raise even though data is missing
    asyncio.run(update_sensors_service(hass, call))
