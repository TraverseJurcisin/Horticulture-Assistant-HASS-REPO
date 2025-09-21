import json
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import (
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    DOMAIN,
    PROFILE_SCOPE_DEFAULT,
)
from custom_components.horticulture_assistant.profile import store as profile_store
from custom_components.horticulture_assistant.profile.schema import (
    PlantProfile,
)
from custom_components.horticulture_assistant.profile_registry import ProfileRegistry

pytestmark = pytest.mark.asyncio


async def _make_entry(hass, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options or {})
    entry.add_to_hass(hass)
    return entry


async def test_initialize_merges_storage_and_options(hass):
    """Profiles in storage and options are merged."""

    prof = PlantProfile(plant_id="p1", display_name="Stored")
    await profile_store.async_save_profile(hass, prof)

    entry = await _make_entry(hass, {CONF_PROFILES: {"p2": {"name": "Opt"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    ids = {p.plant_id for p in reg.list_profiles()}
    assert ids == {"p1", "p2"}
    assert reg.get("p2").display_name == "Opt"


async def test_async_load_migrates_list_format(hass):
    """Registry converts legacy list storage to dict mapping."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    with patch.object(reg._store, "async_load", return_value=[{"plant_id": "legacy", "display_name": "Legacy"}]):
        await reg.async_load()

    prof = reg.get("legacy")
    assert prof and prof.display_name == "Legacy"


async def test_replace_sensor_updates_entry_and_registry(hass):
    """Replacing a sensor updates both entry options and registry state."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_replace_sensor("p1", "temperature", "sensor.temp")

    assert entry.options[CONF_PROFILES]["p1"]["sensors"]["temperature"] == "sensor.temp"
    prof = reg.get("p1")
    assert prof.general["sensors"]["temperature"] == "sensor.temp"


async def test_replace_sensor_unknown_profile_raises(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    with pytest.raises(ValueError):
        await reg.async_replace_sensor("missing", "temperature", "sensor.temp")


async def test_refresh_species_marks_profile(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_refresh_species("p1")
    prof = reg.get("p1")
    assert prof.last_resolved == "1970-01-01T00:00:00Z"


async def test_refresh_species_unknown_profile(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    with pytest.raises(ValueError):
        await reg.async_refresh_species("bad")


async def test_export_creates_file_with_profiles(hass, tmp_path):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    path = tmp_path / "profiles.json"
    out = await reg.async_export(path)
    assert out == path
    assert path.exists()
    data = json.loads(path.read_text())
    assert data[0]["display_name"] == "Plant"


async def test_summaries_return_serialisable_data(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "humidity", "sensor.h")
    summaries = reg.summaries()
    assert summaries == [
        {
            "plant_id": "p1",
            "name": "Plant",
            "species": None,
            "sensors": {"humidity": "sensor.h"},
            "variables": {},
        }
    ]


async def test_iteration_and_len(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert len(reg) == 1
    assert [p.plant_id for p in reg] == ["p1"]


async def test_multiple_sensor_replacements(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_replace_sensor("p1", "temperature", "sensor.t1")
    await reg.async_replace_sensor("p1", "humidity", "sensor.h1")
    await reg.async_replace_sensor("p1", "temperature", "sensor.t2")

    sensors = entry.options[CONF_PROFILES]["p1"]["sensors"]
    assert sensors == {"temperature": "sensor.t2", "humidity": "sensor.h1"}
    prof = reg.get("p1")
    assert prof.general["sensors"] == sensors


async def test_export_uses_hass_config_path(hass, tmp_path, monkeypatch):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    monkeypatch.setattr(hass, "config", type("cfg", (), {"path": lambda self, p: str(tmp_path / p)})())
    out = await reg.async_export("rel.json")
    assert out == tmp_path / "rel.json"
    assert out.exists()


async def test_replace_sensor_updates_options_without_existing_sensors(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant", "sensors": {}}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "moisture", "sensor.m")
    assert entry.options[CONF_PROFILES]["p1"]["sensors"]["moisture"] == "sensor.m"


async def test_replace_sensor_preserves_other_profiles(hass):
    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {"name": "One"},
                "p2": {"name": "Two"},
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p2", "temperature", "sensor.t")
    assert "sensors" not in entry.options[CONF_PROFILES]["p1"]


async def test_refresh_species_persists_to_store(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_refresh_species("p1")
    loaded = await profile_store.async_load_profile(hass, "p1")
    assert loaded and loaded.last_resolved == "1970-01-01T00:00:00Z"


async def test_get_returns_none_for_missing(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert reg.get("absent") is None


async def test_export_creates_parent_directories(hass, tmp_path):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    nested = tmp_path / "deep" / "dir" / "profiles.json"
    await reg.async_export(nested)
    assert nested.exists()


async def test_replace_sensor_overwrites_previous_value(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "temperature", "sensor.one")
    await reg.async_replace_sensor("p1", "temperature", "sensor.two")
    sensors = entry.options[CONF_PROFILES]["p1"]["sensors"]
    assert sensors["temperature"] == "sensor.two"


async def test_export_round_trip(hass, tmp_path):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    path = tmp_path / "profiles.json"
    await reg.async_export(path)
    text = path.read_text()
    data = json.loads(text)
    assert data[0]["display_name"] == "Plant"


async def test_len_after_additions(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert len(reg) == 1
    await reg.async_replace_sensor("p1", "temperature", "sensor.t")
    assert len(reg) == 1


async def test_add_profile_copy_from(hass):
    """Profiles can be created by copying an existing profile."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant", "sensors": {"temperature": "sensor.t"}}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone", base_id="p1")

    assert pid != "p1"
    sensors = entry.options[CONF_PROFILES][pid]["sensors"]
    assert sensors["temperature"] == "sensor.t"
    prof = reg.get(pid)
    assert prof.general["sensors"]["temperature"] == "sensor.t"
    assert prof.general[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT


async def test_add_profile_custom_scope(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("North Bay", scope="grow_zone")

    assert entry.options[CONF_PROFILES][pid][CONF_PROFILE_SCOPE] == "grow_zone"
    prof = reg.get(pid)
    assert prof is not None
    assert prof.general[CONF_PROFILE_SCOPE] == "grow_zone"


async def test_import_template_creates_profile(hass):
    """Bundled templates can seed new profiles."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_import_template("basil")

    prof = reg.get(pid)
    assert prof and prof.display_name == "Basil"
    assert prof.species == "Ocimum basilicum"
