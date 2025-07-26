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

    def __init__(self) -> None:
        self.created_entry = None
        self.unique_id = None

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        self.created_entry = kwargs
        return {"type": "create_entry", **kwargs}

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass
ha.config_entries.ConfigFlow = ConfigFlowBase
class OptionsFlowBase:
    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs):
        self.created_entry = kwargs
        return {"type": "create_entry", **kwargs}
ha.config_entries.OptionsFlow = OptionsFlowBase
ha.data_entry_flow = sys.modules.get("homeassistant.data_entry_flow", types.ModuleType("homeassistant.data_entry_flow"))
ha.data_entry_flow.FlowResult = getattr(ha.data_entry_flow, "FlowResult", dict)
ha.helpers = sys.modules.get("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha.helpers.selector = sys.modules.get("homeassistant.helpers.selector", types.ModuleType("homeassistant.helpers.selector"))
ha.helpers.selector.BooleanSelector = object
ha.helpers.selector.TextSelector = object
ha.helpers.selector.EntitySelector = object
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
        recorded["hass"] = hass
        return "pid42"

    monkeypatch.setattr(config_flow, "generate_profile", fake_generate)

    flow = Flow()
    flow.hass = object()
    result = asyncio.run(flow.async_step_user({"plant_name": "Tomato"}))
    assert result["type"] == "create_entry"
    assert flow.created_entry["data"]["plant_name"] == "Tomato"
    assert recorded["plant_name"] == "Tomato"
    assert recorded["hass"] is flow.hass
    assert flow.created_entry["data"]["plant_id"] == "pid42"
    assert flow.created_entry["data"]["profile_generated"] is True
    assert flow.unique_id == "pid42"


def test_profile_error(monkeypatch):
    """Handle profile generation failure gracefully."""

    def fail_generate(data, hass=None):
        return ""

    monkeypatch.setattr(config_flow, "generate_profile", fail_generate)

    flow = Flow()
    flow.hass = object()
    result = asyncio.run(flow.async_step_user({"plant_name": "Bad"}))
    assert result["type"] == "create_entry"
    assert flow.created_entry["data"]["profile_generated"] is False


def test_options_flow(monkeypatch):
    recorded = {}

    def fake_generate(data, hass=None, overwrite=False):
        recorded.update(data)
        recorded["overwrite"] = overwrite
        return "pid1"

    monkeypatch.setattr(config_flow, "generate_profile", fake_generate)
    flow = Flow()
    flow.hass = object()
    asyncio.run(flow.async_step_user({"plant_name": "Basil"}))

    entry = types.SimpleNamespace(data=flow.created_entry["data"])
    opt_flow = config_flow.HorticultureAssistantOptionsFlow(entry)
    result = asyncio.run(
        opt_flow.async_step_init({
            "moisture_sensors": "sensor.a",
            "plant_type": "herb",
            "zone_id": "5",
            "enable_auto_approve": True,
        })
    )
    assert result["type"] == "create_entry"
    assert opt_flow._data["moisture_sensors"] == ["sensor.a"]
    assert opt_flow._data["plant_type"] == "herb"
    assert recorded["overwrite"] is True
    assert recorded["plant_type"] == "herb"
    assert recorded["zone_id"] == "5"
    assert recorded["enable_auto_approve"] is True
    assert opt_flow._data["profile_generated"] is True
    assert opt_flow._data["plant_id"] == "pid1"
