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
    Path(__file__).resolve().parents[3]
    / "custom_components/horticulture_assistant/entity_base.py",
)
base_mod = importlib.util.module_from_spec(base_spec)
base_spec.loader.exec_module(base_mod)
HorticultureBaseEntity = base_mod.HorticultureBaseEntity


def test_device_info_model():
    ent = HorticultureBaseEntity("Plant", "pid", model="Tester")
    info = ent.device_info
    assert info["model"] == "Tester"
    assert info["name"] == "Plant"
    assert ("horticulture_assistant", "pid") in info["identifiers"]
