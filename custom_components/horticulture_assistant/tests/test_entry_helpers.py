from pathlib import Path
from types import SimpleNamespace

from custom_components.horticulture_assistant.utils.entry_helpers import (
    get_entry_data,
    get_entry_data_by_plant_id,
    get_entry_plant_info,
    remove_entry_data,
    store_entry_data,
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
    assert get_entry_data(hass, "e1") is stored
    assert get_entry_data(hass, entry) is stored
    assert get_entry_data_by_plant_id(hass, "e1") is stored
    remove_entry_data(hass, "e1")
    assert (
        "horticulture_assistant" not in hass.data or "e1" not in hass.data["horticulture_assistant"]
    )
    assert get_entry_data(hass, "e1") is None
    assert get_entry_data_by_plant_id(hass, "e1") is None


def test_get_entry_data_by_plant_id(tmp_path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="e99", data={"plant_id": "pid99", "plant_name": "Pepper"})
    stored = store_entry_data(hass, entry)
    assert get_entry_data_by_plant_id(hass, "pid99") is stored
