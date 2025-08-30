import importlib.util
import sys
import types
from pathlib import Path

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry

ROOT = Path(__file__).resolve().parents[1]
pkg = types.ModuleType("custom_components")
pkg.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", pkg)

ha_pkg = types.ModuleType("custom_components.horticulture_assistant")
ha_pkg.__path__ = [str(ROOT / "custom_components" / "horticulture_assistant")]
sys.modules.setdefault("custom_components.horticulture_assistant", ha_pkg)

spec = importlib.util.spec_from_file_location(
    "custom_components.horticulture_assistant.diagnostics",
    ROOT / "custom_components" / "horticulture_assistant" / "diagnostics.py",
)
diagnostics = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(diagnostics)
async_get_config_entry_diagnostics = diagnostics.async_get_config_entry_diagnostics

DOMAIN = "horticulture_assistant"


class DummyRegistry:
    def summaries(self):
        return [{"id": "p1"}]


class DummyCoordinator:
    last_update_success = True
    update_interval = 0


@pytest.mark.asyncio
async def test_async_get_config_entry_diagnostics(hass):
    entry = ConfigEntry(
        data={"foo": "bar"},
        options={"api_key": "secret", "profiles": {"p1": {}}},
    )
    entry.entry_id = "1"
    entry.version = 1
    hass.data[DOMAIN] = {
        "profile_registry": DummyRegistry(),
        "coordinator_ai": DummyCoordinator(),
    }

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["options"]["api_key"] is REDACTED
    assert result["profiles"] == [{"id": "p1"}]
    assert result["coordinators"]["coordinator_ai"]["last_update_success"] is True
