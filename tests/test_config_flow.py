import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/config_flow.py"
PACKAGE = "custom_components.horticulture_assistant"
if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant")]
    sys.modules[PACKAGE] = pkg
CONST_PATH = Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/const.py"
const_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.const", CONST_PATH)
const_mod = importlib.util.module_from_spec(const_spec)
sys.modules[const_spec.name] = const_mod
const_spec.loader.exec_module(const_mod)

spec = importlib.util.spec_from_file_location(f"{PACKAGE}.config_flow", MODULE_PATH)
config_flow = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = config_flow

# Minimal Home Assistant stubs
ha = sys.modules.get("homeassistant", types.ModuleType("homeassistant"))
ha.config_entries = sys.modules.get("homeassistant.config_entries", types.ModuleType("homeassistant.config_entries"))
ha.config_entries.ConfigEntry = object
class ConfigFlowBase:
    def __init_subclass__(cls, **kwargs):
        pass
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}
    def async_create_entry(self, **kwargs):
        self.created_entry = kwargs
        return {"type": "create_entry", **kwargs}
ha.config_entries.ConfigFlow = getattr(ha.config_entries, "ConfigFlow", ConfigFlowBase)
ha.data_entry_flow = sys.modules.get("homeassistant.data_entry_flow", types.ModuleType("homeassistant.data_entry_flow"))
ha.data_entry_flow.FlowResult = getattr(ha.data_entry_flow, "FlowResult", dict)
ha.helpers = sys.modules.get("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha.helpers.selector = sys.modules.get("homeassistant.helpers.selector", types.ModuleType("homeassistant.helpers.selector"))
ha.helpers.selector.BooleanSelector = object
ha.helpers.selector.TextSelector = object
sys.modules["homeassistant"] = ha
sys.modules["homeassistant.config_entries"] = ha.config_entries
sys.modules["homeassistant.data_entry_flow"] = ha.data_entry_flow
sys.modules["homeassistant.helpers"] = ha.helpers
sys.modules["homeassistant.helpers.selector"] = ha.helpers.selector

spec.loader.exec_module(config_flow)

Flow = config_flow.HorticultureAssistantConfigFlow


def test_full_flow(monkeypatch):
    recorded = {}
    def fake_generate(data, hass=None):
        recorded.update(data)
        return data.get("plant_name")
    monkeypatch.setattr(config_flow, "generate_profile", fake_generate)

    flow = Flow()
    result = asyncio.run(flow.async_step_user({"plant_name": "Tomato", "zone_id": "9"}))
    assert result["step_id"] == "details"
    result = asyncio.run(flow.async_step_details({"plant_type": "tomato"}))
    assert result["step_id"] == "sensors"
    result = asyncio.run(flow.async_step_sensors({"moisture_sensors": "sensor.moist"}))
    assert result["type"] == "create_entry"
    assert flow.created_entry["data"]["plant_name"] == "Tomato"
    assert recorded["plant_name"] == "Tomato"
    assert flow.created_entry["data"]["moisture_sensors"] == ["sensor.moist"]
