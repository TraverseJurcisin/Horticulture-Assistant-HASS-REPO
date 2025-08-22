import sys
import types

import pytest

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
sys.modules.setdefault("homeassistant.helpers.entity_registry", types.ModuleType("homeassistant.helpers.entity_registry"))
sys.modules.setdefault("homeassistant.helpers.event", types.ModuleType("homeassistant.helpers.event"))
sys.modules.setdefault("homeassistant.helpers.update_coordinator", types.ModuleType("homeassistant.helpers.update_coordinator"))
util = types.ModuleType("homeassistant.util")
util.slugify = lambda x: x
sys.modules.setdefault("homeassistant.util", util)

from custom_components.horticulture_assistant.resolver import resolve_variable_from_source


@pytest.mark.asyncio
async def test_resolve_manual(hass):
    res = await resolve_variable_from_source(
        hass, plant_id="p1", key="temp", source="manual", manual_value=21
    )
    assert res.value == 21
    assert res.source == "manual"
    assert res.citations[0].source == "manual"


@pytest.mark.asyncio
async def test_resolve_clone(hass, monkeypatch):
    async def fake_get(hass, plant_id):
        return {
            "plant_id": "src",
            "display_name": "src",
            "variables": {"temp": {"value": 10, "source": "manual", "citations": []}},
        }

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile.store.async_get_profile",
        fake_get,
    )
    res = await resolve_variable_from_source(
        hass,
        plant_id="p2",
        key="temp",
        source="clone",
        clone_from="src",
    )
    assert res.value == 10
    assert res.source == "clone"
    assert res.citations[0].details["profile_id"] == "src"


@pytest.mark.asyncio
async def test_resolve_opb(hass, monkeypatch):
    async def fake_fetch(hass, species, field):
        return 7, "http://example.com"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.opb_client.async_fetch_field",
        fake_fetch,
    )
    res = await resolve_variable_from_source(
        hass,
        plant_id="p3",
        key="temp",
        source="openplantbook",
        opb_args={"species": "mint", "field": "temperature"},
    )
    assert res.value == 7
    assert res.citations[0].url == "http://example.com"


@pytest.mark.asyncio
async def test_resolve_ai(hass, monkeypatch):
    async def fake_ai(hass, key, plant_id, **kwargs):
        return {"value": 5, "summary": "ai", "links": ["http://ai"]}

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.ai_client.async_recommend_variable",
        fake_ai,
    )
    res = await resolve_variable_from_source(
        hass,
        plant_id="p4",
        key="temp",
        source="ai",
    )
    assert res.value == 5
    assert res.citations[0].details["links"] == ["http://ai"]
