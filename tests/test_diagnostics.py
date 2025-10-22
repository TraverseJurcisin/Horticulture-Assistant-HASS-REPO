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
    def diagnostics_snapshot(self):
        return [
            {
                "summary": {
                    "plant_id": "p1",
                    "name": "P1",
                    "profile_type": "line",
                    "species": None,
                    "tenant_id": None,
                    "parents": [],
                    "sensors": {},
                    "targets": {},
                    "tags": [],
                    "last_resolved": None,
                },
                "run_history": [{"run_id": "run-1", "profile_id": "p1", "species_id": None, "started_at": "2024-01-01"}],
                "harvest_history": [],
                "statistics": [],
                "lineage": [],
            }
        ]


class DummyCoordinator:
    last_update_success = True
    update_interval = 0
    last_update = "2024-01-01T00:00:00"
    last_exception = None


@pytest.mark.asyncio
async def test_async_get_config_entry_diagnostics(hass):
    entry = ConfigEntry(
        data={"foo": "bar"},
        options={"api_key": "secret", "profiles": {"p1": {}}},
    )
    entry.entry_id = "1"
    entry.version = 1
    hass.data[DOMAIN] = {
        "registry": DummyRegistry(),
        "coordinator_ai": DummyCoordinator(),
    }

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["options"]["api_key"] is REDACTED
    assert result["profile_count"] == 1
    assert result["profiles"][0]["summary"]["plant_id"] == "p1"
    assert result["profile_totals"]["run_events"] == 1
    assert result["coordinators"]["coordinator_ai"]["last_update_success"] is True
    assert "last_update" in result["coordinators"]["coordinator_ai"]
    assert "last_exception" in result["coordinators"]["coordinator_ai"]
    assert result["schema_version"] == 3
