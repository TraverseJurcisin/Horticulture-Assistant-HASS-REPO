import sys
import types
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.horticulture_assistant.resolver import generate_profile

ha = types.ModuleType("homeassistant")
ha.const = types.SimpleNamespace(Platform=types.SimpleNamespace(SENSOR="sensor"))
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.const", ha.const)
config_entries = types.ModuleType("homeassistant.config_entries")


class ConfigEntry:  # minimal stub
    pass


config_entries.ConfigEntry = ConfigEntry
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.exceptions", types.ModuleType("homeassistant.exceptions"))
helpers = types.ModuleType("homeassistant.helpers")
sys.modules.setdefault("homeassistant.helpers", helpers)
sys.modules.setdefault(
    "homeassistant.helpers.entity_registry",
    types.ModuleType("homeassistant.helpers.entity_registry"),
)
sys.modules.setdefault("homeassistant.helpers.event", types.ModuleType("homeassistant.helpers.event"))
update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")


class _DUC:
    def __class_getitem__(cls, _item):
        return cls


update_coordinator.DataUpdateCoordinator = _DUC
update_coordinator.UpdateFailed = Exception
sys.modules.setdefault("homeassistant.helpers.update_coordinator", update_coordinator)
util = types.ModuleType("homeassistant.util")
util.slugify = lambda x: x
sys.modules.setdefault("homeassistant.util", util)


class DummyEntry:
    def __init__(self, options):
        self.options = options


def make_hass():
    def update_entry(entry, *, options):
        entry.options = options

    return types.SimpleNamespace(
        config_entries=types.SimpleNamespace(async_update_entry=update_entry),
        helpers=types.SimpleNamespace(aiohttp_client=types.SimpleNamespace(async_get_clientsession=AsyncMock())),
    )


@pytest.mark.asyncio
async def test_generate_profile_persists_to_store(monkeypatch):
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "p1": {"name": "Plant"},
                "src": {"thresholds": {"temp_c_min": 7.0}},
            }
        }
    )
    saved = []

    async def fake_save(hass, profile):
        saved.append(profile)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store.async_save_profile",
        fake_save,
    )
    with patch(
        "custom_components.horticulture_assistant.resolver.PreferenceResolver.resolve_profile",
        AsyncMock(),
    ):
        await generate_profile(hass, entry, "p1", "clone", source_profile_id="src")
    assert saved and saved[0]["plant_id"] == "p1"
    target = saved[0]["resolved_targets"]["temp_c_min"]
    assert target["annotation"]["source_type"] == "clone"


@pytest.mark.asyncio
async def test_async_load_profile_returns_dataclass(monkeypatch):
    sample = {
        "plant_id": "p1",
        "display_name": "Plant",
        "resolved_targets": {
            "temp": {
                "value": 1,
                "annotation": {"source_type": "manual"},
                "citations": [],
            }
        },
    }

    async def fake_get(_hass, _pid):
        return sample

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store.async_get_profile",
        fake_get,
    )

    from custom_components.horticulture_assistant.profile.store import (
        async_load_profile,
    )

    profile = await async_load_profile(None, "p1")
    assert profile.plant_id == "p1"
    assert profile.resolved_targets["temp"].value == 1
    assert profile.resolved_targets["temp"].annotation.source_type == "manual"


@pytest.mark.asyncio
async def test_async_load_profiles_returns_dataclasses(monkeypatch):
    samples = {
        "p1": {"plant_id": "p1", "display_name": "One", "resolved_targets": {}},
        "p2": {
            "plant_id": "p2",
            "display_name": "Two",
            "resolved_targets": {
                "temp": {
                    "value": 2,
                    "annotation": {"source_type": "manual"},
                    "citations": [],
                }
            },
        },
    }

    async def fake_load_all(_hass):
        return samples

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store.async_load_all",
        fake_load_all,
    )

    from custom_components.horticulture_assistant.profile.store import (
        async_load_profiles,
    )

    profiles = await async_load_profiles(None)
    assert set(profiles) == {"p1", "p2"}
    assert profiles["p2"].resolved_targets["temp"].value == 2


@pytest.mark.asyncio
async def test_async_save_profile_accepts_dataclass(monkeypatch):
    saved: dict[str, dict[str, Any]] = {}

    class DummyStore:
        async def async_save(self, data):
            saved.update(data)

    async def fake_load_all(_hass):
        return {}

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store._store",
        lambda hass: DummyStore(),
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store.async_load_all",
        fake_load_all,
    )

    from custom_components.horticulture_assistant.profile.schema import (
        BioProfile,
        FieldAnnotation,
        ResolvedTarget,
    )
    from custom_components.horticulture_assistant.profile.store import (
        async_save_profile,
    )

    profile = BioProfile(
        profile_id="p1",
        display_name="Plant",
        resolved_targets={"temp": ResolvedTarget(value=1, annotation=FieldAnnotation(source_type="manual"))},
    )

    await async_save_profile(None, profile)
    assert saved["p1"]["display_name"] == "Plant"
    assert saved["p1"]["resolved_targets"]["temp"]["value"] == 1
    assert saved["p1"]["library"]["profile_id"] == "p1"
    assert saved["p1"]["local"]["general"] == {}
