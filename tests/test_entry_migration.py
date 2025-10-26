import importlib

import pytest

import tests.conftest  # noqa: F401 - ensure HA stubs are registered
from custom_components.horticulture_assistant.const import (
    CONF_KEEP_STALE,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_KEEP_STALE,
    DOMAIN,
    PROFILE_SCOPE_DEFAULT,
)


class DummyConfigEntry:
    def __init__(self, *, version, data=None, options=None, entry_id="entry", title="Horti"):
        self.version = version
        self.data = data or {}
        self.options = options or {}
        self.entry_id = entry_id
        self.title = title
        self.domain = DOMAIN


@pytest.mark.asyncio
async def test_migrate_entry_materialises_profile_payload(hass):
    module = importlib.import_module("custom_components.horticulture_assistant.__init__")
    assert hasattr(module, "async_migrate_entry"), dir(module)
    async_migrate_entry = module.async_migrate_entry
    entry = DummyConfigEntry(
        version=1,
        data={
            CONF_PLANT_ID: "alpha",
            CONF_PLANT_NAME: "Alpha Plant",
            CONF_PLANT_TYPE: "herb",
            CONF_UPDATE_INTERVAL: 30,
        },
        options={
            "sensors": {"moisture": "sensor.alpha"},
            "thresholds": {"moisture_min": 10},
            "species_display": "Basil",
        },
    )
    hass.config_entries._entries[entry.entry_id] = entry

    await async_migrate_entry(hass, entry)

    assert entry.version == 3
    assert entry.options[CONF_KEEP_STALE] == DEFAULT_KEEP_STALE
    assert entry.options["thresholds"]["moisture_min"] == 10
    profile_map = entry.options[CONF_PROFILES]
    assert "alpha" in profile_map

    profile = profile_map["alpha"]
    assert profile["name"] == "Alpha Plant"
    assert profile["general"]["plant_type"] == "herb"
    assert profile["general"]["sensors"]["moisture"] == "sensor.alpha"
    assert profile["general"][CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert profile["species_display"] == "Basil"
    assert "sections" in profile and "library" in profile and "local" in profile
    assert entry.options["sensors"]["moisture"] == "sensor.alpha"


@pytest.mark.asyncio
async def test_migrate_entry_preserves_existing_profiles(hass):
    module = importlib.import_module("custom_components.horticulture_assistant.__init__")
    assert hasattr(module, "async_migrate_entry"), dir(module)
    async_migrate_entry = module.async_migrate_entry
    entry = DummyConfigEntry(
        version=2,
        data={CONF_PLANT_ID: "beta", CONF_PLANT_NAME: "Beta"},
        options={
            CONF_PROFILES: {
                "beta": {
                    "name": "Beta",
                    "sensors": {"temperature": "sensor.temp"},
                    "citations": {"temperature": {"mode": "manual"}},
                }
            }
        },
    )
    hass.config_entries._entries[entry.entry_id] = entry

    await async_migrate_entry(hass, entry)

    assert entry.version == 3
    profile = entry.options[CONF_PROFILES]["beta"]
    assert profile["general"]["sensors"]["temperature"] == "sensor.temp"
    assert profile["general"][CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert profile["citations"]["temperature"]["mode"] == "manual"
    assert "sections" in profile and "library" in profile and "local" in profile
