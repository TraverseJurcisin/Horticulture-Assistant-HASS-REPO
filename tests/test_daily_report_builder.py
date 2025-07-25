import json
import types
import sys
from pathlib import Path

ha = types.ModuleType("homeassistant")
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.core", ha.core)

from custom_components.horticulture_assistant.utils import daily_report_builder as drb  # noqa: E402

class DummyConfig:
    def __init__(self, base: Path):
        self._base = Path(base)
    def path(self, *parts):
        return str(self._base.joinpath(*parts))

class DummyStates:
    def __init__(self):
        self._data = {}
    def get(self, entity_id):
        val = self._data.get(entity_id)
        return types.SimpleNamespace(state=str(val)) if val is not None else None

class DummyHass:
    def __init__(self, base: Path):
        self.config = DummyConfig(base)
        self.states = DummyStates()


def test_build_daily_report(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {
        "general": {
            "plant_type": "citrus",
            "lifecycle_stage": "fruiting",
            "sensor_entities": {"temperature": "sensor.p1_temp"},
        },
        "thresholds": {"light": 100},
        "nutrients": {"N": 120},
    }
    (plants / "plant1.json").write_text(json.dumps(profile))

    registry = {"plant1": {"plant_type": "citrus"}}
    (tmp_path / "plant_registry.json").write_text(json.dumps(registry))

    hass = DummyHass(tmp_path)
    hass.states._data["sensor.p1_temp"] = "25"

    report = drb.build_daily_report(hass, "plant1")
    assert report.temperature == 25.0
    assert report.environment_targets["temp_c"] == [18, 28]


def test_build_daily_report_multiple_sensors(tmp_path):
    plants = tmp_path / "plants"
    plants.mkdir()
    profile = {
        "general": {
            "plant_type": "citrus",
            "sensor_entities": {
                "moisture_sensors": ["sensor.m1", "sensor.m2"],
            },
        }
    }
    (plants / "p2.json").write_text(json.dumps(profile))
    registry = {"p2": {"plant_type": "citrus"}}
    (tmp_path / "plant_registry.json").write_text(json.dumps(registry))

    hass = DummyHass(tmp_path)
    hass.states._data["sensor.m1"] = "30"
    hass.states._data["sensor.m2"] = "40"

    report = drb.build_daily_report(hass, "p2")
    assert report.moisture == 35.0

