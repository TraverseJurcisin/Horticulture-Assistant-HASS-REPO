import importlib
import sys
import types
from pathlib import Path

# Import base entity
PACKAGE = "custom_components.horticulture_assistant"
ha = types.ModuleType("homeassistant")
ha.helpers = types.ModuleType("homeassistant.helpers")
ha.helpers.entity = types.ModuleType("homeassistant.helpers.entity")
ha.helpers.entity.Entity = object
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.helpers", ha.helpers)
sys.modules.setdefault("homeassistant.helpers.entity", ha.helpers.entity)

base_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.entity_base",
    Path(__file__).resolve().parents[3] / "custom_components/horticulture_assistant/entity_base.py",
)
base_mod = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base_mod)
HorticultureBaseEntity = base_mod.HorticultureBaseEntity
HorticultureEntryEntity = base_mod.HorticultureEntryEntity


def test_device_info_model():
    ent = HorticultureBaseEntity("entry-1", "Plant", "pid", model="Tester")
    info = ent.device_info
    assert info["model"] == "Tester"
    assert info["name"] == "Plant"
    assert ("horticulture_assistant", "entry-1:profile:pid") in info["identifiers"]
    assert info["via_device"] == ("horticulture_assistant", "entry:entry-1")


def test_entry_entity_device_info_defaults():
    ent = HorticultureEntryEntity("entry-1", default_device_name="Plant Entry")
    info = ent.device_info
    assert info["identifiers"] == {("horticulture_assistant", "entry:entry-1")}
    assert info["name"] == "Plant Entry"
    assert info["manufacturer"] == "Horticulture Assistant"
