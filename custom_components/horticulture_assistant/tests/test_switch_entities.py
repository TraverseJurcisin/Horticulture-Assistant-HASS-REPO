import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "custom_components/horticulture_assistant/switch.py"
)
PACKAGE = "custom_components.horticulture_assistant"
if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [
        str(
            Path(__file__).resolve().parents[3]
            / "custom_components/horticulture_assistant"
        )
    ]
    sys.modules[PACKAGE] = pkg
CONST_PATH = (
    Path(__file__).resolve().parents[3]
    / "custom_components/horticulture_assistant/const.py"
)
const_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.const", CONST_PATH)
const_mod = importlib.util.module_from_spec(const_spec)
sys.modules[const_spec.name] = const_mod
const_spec.loader.exec_module(const_mod)

spec = importlib.util.spec_from_file_location(f"{PACKAGE}.switch", MODULE_PATH)
switch = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = switch

# Minimal Home Assistant stubs
ha = types.ModuleType("homeassistant")
ha.components = types.ModuleType("homeassistant.components")
ha_switch_mod = types.ModuleType("homeassistant.components.switch")


class SwitchEntity:
    def __init__(self):
        self._attr_is_on = False
        self._attr_name = ""

    @property
    def is_on(self):
        return self._attr_is_on

    @property
    def name(self):
        return self._attr_name

    def async_write_ha_state(self):
        return None


ha_switch_mod.SwitchEntity = SwitchEntity
ha.components.switch = ha_switch_mod
ha.config_entries = types.ModuleType("homeassistant.config_entries")
ha.config_entries.ConfigEntry = object
ha.core = types.ModuleType("homeassistant.core")
ha.core.HomeAssistant = object
ha.helpers = types.ModuleType("homeassistant.helpers")
ha.helpers.entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
ha.helpers.entity_platform.AddEntitiesCallback = object
ha.helpers.entity = types.ModuleType("homeassistant.helpers.entity")
ha.helpers.entity.Entity = object
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.components"] = ha.components
sys.modules["homeassistant.components.switch"] = ha_switch_mod
sys.modules["homeassistant.config_entries"] = ha.config_entries
sys.modules["homeassistant.core"] = ha.core
sys.modules["homeassistant.helpers"] = ha.helpers
sys.modules["homeassistant.helpers.entity"] = ha.helpers.entity
sys.modules["homeassistant.helpers.entity_platform"] = ha.helpers.entity_platform

spec.loader.exec_module(switch)

IrrigationSwitch = switch.IrrigationSwitch
FertigationSwitch = switch.FertigationSwitch


class DummyHass:
    def __init__(self):
        pass


def test_switch_operations():
    hass = DummyHass()
    irr = IrrigationSwitch(hass, "Plant", "pid")
    fert = FertigationSwitch(hass, "Plant", "pid")

    asyncio.run(irr.async_turn_on())
    assert irr.is_on
    asyncio.run(irr.async_turn_off())
    assert not irr.is_on

    asyncio.run(fert.async_turn_on())
    assert fert.is_on
    asyncio.run(fert.async_turn_off())
    assert not fert.is_on
