import json
from pathlib import Path

from custom_components.horticulture_assistant.utils.plant_registry import (
    get_plant_metadata,
    get_plant_type,
)


class DummyConfig:
    def __init__(self, base: Path):
        self._base = Path(base)

    def path(self, name: str) -> str:
        return str(self._base / name)


class DummyHass:
    def __init__(self, base: Path):
        self.config = DummyConfig(base)


def test_get_plant_type(tmp_path: Path):
    registry = {"p1": {"plant_type": "tomato"}}
    (tmp_path / "plant_registry.json").write_text(json.dumps(registry))

    hass = DummyHass(tmp_path)

    assert get_plant_type("p1", hass) == "tomato"
    assert get_plant_metadata("p1", hass)["plant_type"] == "tomato"
    assert get_plant_type("missing", hass) is None
