from types import SimpleNamespace
from pathlib import Path
from custom_components.horticulture_assistant.utils.entry_helpers import (
    get_entry_plant_info,
    store_entry_data,
    remove_entry_data,
)

class DummyEntry(SimpleNamespace):
    pass

def test_get_entry_plant_info_defaults():
    entry = DummyEntry(entry_id="eid", data={})
    pid, name = get_entry_plant_info(entry)
    assert pid == "eid"
    assert name.startswith("Plant ")

def test_get_entry_plant_info_explicit():
    entry = DummyEntry(entry_id="eid", data={"plant_id": "pid1", "plant_name": "Tom"})
    pid, name = get_entry_plant_info(entry)
    assert pid == "pid1"
    assert name == "Tom"


class DummyHass(SimpleNamespace):
    def __init__(self, base: str):
        super().__init__(config=SimpleNamespace(path=lambda n: f"{base}/{n}"))
        self.data = {}


def test_store_and_remove_entry_data(tmp_path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="e1", data={"plant_name": "Tomato"})
    stored = store_entry_data(hass, entry)
    assert hass.data
    assert hass.data["horticulture_assistant"]["e1"] is stored
    assert stored["profile_dir"] == Path(tmp_path / "plants/e1")
    remove_entry_data(hass, "e1")
    assert "e1" not in hass.data["horticulture_assistant"]
