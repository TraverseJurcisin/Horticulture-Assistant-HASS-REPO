from types import SimpleNamespace
from custom_components.horticulture_assistant.utils.entry_helpers import get_entry_plant_info

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
