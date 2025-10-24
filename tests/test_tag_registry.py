import json
import sys
import types
from enum import Enum

sensor_module = sys.modules.get("homeassistant.components.sensor")
if sensor_module is None:
    sensor_module = types.ModuleType("homeassistant.components.sensor")
    sys.modules["homeassistant.components.sensor"] = sensor_module
    components_pkg = sys.modules.setdefault(
        "homeassistant.components", types.ModuleType("homeassistant.components")
    )
    components_pkg.sensor = sensor_module

if not hasattr(sensor_module, "SensorEntity"):
    class SensorEntity:  # type: ignore[too-few-public-methods]
        """Minimal stand-in used in tests without Home Assistant."""

    sensor_module.SensorEntity = SensorEntity

if not hasattr(sensor_module, "SensorStateClass"):
    class SensorStateClass(str, Enum):
        MEASUREMENT = "measurement"

    sensor_module.SensorStateClass = SensorStateClass

from custom_components.horticulture_assistant.utils import tag_registry


def _prepare_tags(tmp_path, data):
    path = tmp_path / "tags.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    tag_registry._load_tags.cache_clear()
    return path


def test_get_plants_with_tag_returns_copy(tmp_path, monkeypatch):
    path = _prepare_tags(tmp_path, {"herb": ["basil"]})
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", path)

    plants = tag_registry.get_plants_with_tag("herb")
    plants.append("mint")

    again = tag_registry.get_plants_with_tag("herb")
    assert again == ["basil"]


def test_search_tags_returns_copies(tmp_path, monkeypatch):
    path = _prepare_tags(
        tmp_path,
        {
            "herb": ["basil"],
            "herbal": ["tarragon"],
            "flower": ["rose"],
        },
    )
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", path)

    results = tag_registry.search_tags("herb")
    results["herb"].append("mint")

    again = tag_registry.search_tags("her")
    assert again == {"herb": ["basil"], "herbal": ["tarragon"]}
