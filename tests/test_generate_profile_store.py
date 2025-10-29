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
async def test_async_load_all_supports_missing_hass(monkeypatch):
    from custom_components.horticulture_assistant.profile import store as store_mod

    class DummyStore:
        def __init__(self) -> None:
            self.calls = 0

        async def async_load(self) -> dict[str, dict[str, Any]]:
            self.calls += 1
            if self.calls == 1:
                return {"p1": {"plant_id": "p1"}}
            return {}

    dummy_store = DummyStore()

    monkeypatch.setattr(store_mod, "_store", lambda hass: dummy_store)
    monkeypatch.setattr(store_mod, "_FALLBACK_CACHE", {}, raising=False)

    first = await store_mod.async_load_all(None)
    assert first == {"p1": {"plant_id": "p1"}}

    second = await store_mod.async_load_all(None)
    assert second == first
    assert dummy_store.calls == 2


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


@pytest.mark.asyncio
async def test_async_save_profile_preserves_metadata(monkeypatch):
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

    from custom_components.horticulture_assistant.profile.store import (
        async_save_profile,
    )

    payload = {
        "plant_id": "p1",
        "profile_id": "p1",
        "display_name": "Plant",
        "species_display": "Sweet Basil",
        "species_pid": "obp123",
        "image_url": "https://example.invalid/plant.png",
        "opb_credentials": {"client_id": "id", "secret": "sec"},
    }

    await async_save_profile(None, payload)

    stored = saved["p1"]
    assert stored["species_display"] == "Sweet Basil"
    assert stored["species_pid"] == "obp123"
    assert stored["image_url"] == "https://example.invalid/plant.png"
    assert stored["opb_credentials"] == {"client_id": "id", "secret": "sec"}


@pytest.mark.asyncio
async def test_async_save_profile_preserves_numeric_species_pid(monkeypatch):
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

    from custom_components.horticulture_assistant.profile.store import async_save_profile

    payload = {
        "plant_id": "p2",
        "profile_id": "p2",
        "display_name": "Numeric Plant",
        "species_display": "Tomato",
        "species_pid": 24680,
    }

    await async_save_profile(None, payload)

    stored = saved["p2"]
    assert stored["species_pid"] == "24680"
    assert stored["species_display"] == "Tomato"


@pytest.mark.asyncio
async def test_async_save_profile_accepts_mapping_proxy_credentials(monkeypatch):
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

    from custom_components.horticulture_assistant.profile.store import (
        async_save_profile,
    )

    payload = {
        "plant_id": "p1",
        "profile_id": "p1",
        "display_name": "Plant",
        "opb_credentials": types.MappingProxyType({"client_id": "id", "secret": "sec"}),
    }

    await async_save_profile(None, payload)

    stored = saved["p1"]
    assert stored["opb_credentials"] == {"client_id": "id", "secret": "sec"}


@pytest.mark.asyncio
async def test_async_save_profile_handles_credentials_with_stub_hass(monkeypatch):
    saved: dict[str, dict[str, Any]] = {}

    class DummyStore:
        async def async_save(self, data):
            saved.update(data)

    async def fake_load_all(_hass):
        return {}

    hass = types.SimpleNamespace(data={})

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store._store",
        lambda _hass: DummyStore(),
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store.async_load_all",
        fake_load_all,
    )

    from custom_components.horticulture_assistant.profile.store import async_save_profile

    payload = {
        "plant_id": "p1",
        "profile_id": "p1",
        "display_name": "Plant",
        "opb_credentials": types.MappingProxyType({"client_id": "id", "secret": "sec"}),
    }

    await async_save_profile(hass, payload)

    stored = saved["p1"]
    assert stored["opb_credentials"] == {"client_id": "id", "secret": "sec"}
