"""Tests for helper utilities that derive profile defaults from entries."""

from __future__ import annotations

import pytest

from custom_components.horticulture_assistant.const import (
    CONF_PLANT_ID,
    CONF_PROFILES,
    DOMAIN,
)
from custom_components.horticulture_assistant.utils.entry_helpers import (
    BY_PLANT_ID,
    ProfileContext,
    ProfileContextCollection,
    build_entry_snapshot,
    get_entry_plant_info,
    get_primary_profile_id,
    get_primary_profile_sensors,
    get_primary_profile_thresholds,
    resolve_profile_context_collection,
    entry_device_identifier,
    profile_device_identifier,
    serialise_device_info,
    resolve_entry_device_info,
    resolve_profile_device_info,
    resolve_profile_image_url,
    store_entry_data,
    update_entry_data,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry


def _make_entry(*, data=None, options=None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=data or {}, options=options or {})
    entry.add_to_hass = lambda hass: None  # noqa: D401 - satisfy MockConfigEntry interface
    return entry


def test_primary_profile_id_prefers_entry_data():
    entry = _make_entry(data={CONF_PLANT_ID: "alpha"})
    assert get_primary_profile_id(entry) == "alpha"


def test_primary_profile_id_falls_back_to_profile_map():
    entry = _make_entry(options={CONF_PROFILES: {"beta": {"name": "Beta"}}})
    assert get_primary_profile_id(entry) == "beta"


def test_entry_plant_info_prefers_profile_name():
    entry = _make_entry(
        options={CONF_PROFILES: {"p1": {"name": "Rose"}}},
        data={CONF_PLANT_ID: "p1", "plant_name": "Fallback"},
    )
    assert get_entry_plant_info(entry) == ("p1", "Rose")


def test_entry_snapshot_collects_sensors_and_thresholds():
    entry = _make_entry(
        options={
            CONF_PROFILES: {
                "p1": {
                    "name": "Lavender",
                    "sensors": {"temperature": "sensor.temp"},
                    "thresholds": {"temperature_min": 12},
                }
            }
        }
    )
    snap = build_entry_snapshot(entry)
    assert snap["plant_id"] == "p1"
    assert snap["sensors"]["temperature"] == "sensor.temp"
    assert snap["thresholds"]["temperature_min"] == 12


def test_primary_sensors_use_top_level_mapping():
    entry = _make_entry(options={"sensors": {"temperature": "sensor.temp"}})
    assert get_primary_profile_sensors(entry) == {"temperature": "sensor.temp"}


def test_primary_sensors_from_profile_payload():
    entry = _make_entry(
        options={
            CONF_PROFILES: {
                "gamma": {
                    "name": "Gamma",
                    "sensors": {"humidity": "sensor.hum"},
                }
            }
        }
    )
    assert get_primary_profile_sensors(entry) == {"humidity": "sensor.hum"}


def test_primary_thresholds_prefer_entry_options():
    entry = _make_entry(options={"thresholds": {"lux_to_ppfd": 0.02}})
    assert get_primary_profile_thresholds(entry)["lux_to_ppfd"] == 0.02


def test_primary_thresholds_from_profile_resolved_targets():
    entry = _make_entry(
        options={
            CONF_PROFILES: {
                "delta": {
                    "name": "Delta",
                    "resolved_targets": {"lux_to_ppfd": {"value": 0.5}},
                }
            }
        }
    )
    assert get_primary_profile_thresholds(entry)["lux_to_ppfd"] == 0.5


@pytest.mark.asyncio
async def test_store_entry_data_tracks_snapshot(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "p2", "plant_name": "Stored"},
        options={CONF_PROFILES: {"p2": {"name": "Stored", "sensors": {"moisture": "sensor.moist"}}}},
    )
    stored = store_entry_data(hass, entry)
    assert stored["plant_id"] == "p2"
    assert stored["snapshot"]["sensors"]["moisture"] == "sensor.moist"
    assert hass.data[DOMAIN][entry.entry_id] is stored


@pytest.mark.asyncio
async def test_update_entry_data_refreshes_mapping(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "old", "plant_name": "Old"},
        options={CONF_PROFILES: {"old": {"name": "Old"}}},
    )
    store_entry_data(hass, entry)
    entry.options = {CONF_PROFILES: {"new": {"name": "New"}, "child": {"name": "Child"}}}
    entry.data = {CONF_PLANT_ID: "new", "plant_name": "New"}
    refreshed = update_entry_data(hass, entry)
    assert refreshed["plant_id"] == "new"
    mapping = hass.data[DOMAIN][BY_PLANT_ID]
    assert mapping["new"] is refreshed
    assert mapping["child"] is refreshed
    assert "old" not in mapping
    assert refreshed["profile_ids"] == ["child", "new"]
    profile_devices = refreshed["profile_devices"]
    assert set(profile_devices) == {"child", "new"}
    assert profile_devices["new"]["name"] == "New"
    assert profile_devices["child"]["name"] == "Child"

    contexts = refreshed["profile_contexts"]
    assert set(contexts) == {"child", "new"}
    assert contexts["new"]["name"] == "New"
    assert contexts["child"]["name"] == "Child"


@pytest.mark.asyncio
async def test_store_entry_data_populates_device_info(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "p2", CONF_PLANT_NAME: "Stored"},
        options={
            CONF_PROFILES: {
                "p2": {"name": "Stored", "general": {"plant_type": "herb", "area": "Kitchen"}}
            }
        },
    )
    stored = store_entry_data(hass, entry)
    entry_info = stored["entry_device_info"]
    assert entry_info["name"] == "Stored"
    assert entry_device_identifier(entry.entry_id) in entry_info["identifiers"]

    profile_devices = stored["profile_devices"]
    assert "p2" in profile_devices
    profile_info = profile_devices["p2"]
    assert profile_device_identifier(entry.entry_id, "p2") in profile_info["identifiers"]
    assert profile_info["name"] == "Stored"
    assert profile_info.get("suggested_area") == "Kitchen"

    contexts = stored["profile_contexts"]
    assert "p2" in contexts
    ctx = contexts["p2"]
    assert ctx["name"] == "Stored"
    assert ctx["sensors"] == {"moisture": ["sensor.moist"]}


@pytest.mark.asyncio
async def test_resolve_profile_device_info_tracks_updates(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "alpha", CONF_PLANT_NAME: "Alpha"},
        options={CONF_PROFILES: {"alpha": {"name": "Alpha"}}},
    )
    store_entry_data(hass, entry)
    info = resolve_profile_device_info(hass, entry.entry_id, "alpha")
    assert info["name"] == "Alpha"

    entry.options = {CONF_PROFILES: {"alpha": {"name": "Renamed"}}}
    update_entry_data(hass, entry)
    updated = resolve_profile_device_info(hass, entry.entry_id, "alpha")
    assert updated["name"] == "Renamed"


@pytest.mark.asyncio
async def test_resolve_entry_device_info_returns_metadata(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "beta", CONF_PLANT_NAME: "Beta"},
        options={CONF_PROFILES: {"beta": {"name": "Beta"}}},
    )
    store_entry_data(hass, entry)
    info = resolve_entry_device_info(hass, entry.entry_id)
    assert info is not None
    assert entry_device_identifier(entry.entry_id) in info["identifiers"]
    assert info["name"] == "Beta"


@pytest.mark.asyncio
async def test_resolve_profile_image_url_prefers_profile_metadata(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "primary", "plant_name": "Primary"},
        options={
            "image_url": "https://example.com/entry.png",
            CONF_PROFILES: {
                "primary": {"name": "Primary", "image": "https://example.com/profile.png"},
                "child": {"name": "Child", "image_url": "https://example.com/child.png"},
            },
        },
    )

    store_entry_data(hass, entry)

    child_image = resolve_profile_image_url(hass, entry.entry_id, "child")
    assert child_image == "https://example.com/child.png"

    primary_image = resolve_profile_image_url(hass, entry.entry_id, "primary")
    assert primary_image == "https://example.com/profile.png"

    fallback_image = resolve_profile_image_url(hass, entry.entry_id, "missing")
    assert fallback_image == "https://example.com/entry.png"


def test_profile_context_helpers_normalise_payload():
    context = ProfileContext(
        id="plant",
        name="Plant",
        sensors={"temperature": ["sensor.temp", "sensor.temp_2"], "humidity": "sensor.hum"},
        thresholds={"temperature_min": 12},
        payload={"name": "Plant"},
        device_info={
            "name": "Plant",
            "identifiers": {(DOMAIN, "profile:plant")},
        },
    )

    assert context.sensor_ids_for_roles("temperature") == ("sensor.temp", "sensor.temp_2")
    assert context.first_sensor("humidity") == "sensor.hum"
    assert context.has_sensors("temperature", "humidity") is True
    assert context.has_sensors("light") is False
    assert context.has_sensors() is True
    assert context.get_threshold("temperature_min") == 12
    info = context.as_device_info()
    assert info["name"] == "Plant"
    assert (DOMAIN, "profile:plant") in info["identifiers"]


@pytest.mark.asyncio
async def test_resolve_profile_context_collection_aggregates_profiles(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "alpha", CONF_PLANT_NAME: "Alpha"},
        options={
            CONF_PROFILES: {
                "alpha": {
                    "name": "Alpha",
                    "sensors": {"temperature": ["sensor.temp", "sensor.temp_backup"], "humidity": "sensor.hum"},
                    "thresholds": {"temperature_min": 10},
                },
                "beta": {"name": "Beta"},
            },
            "thresholds": {"humidity_max": 85},
        },
    )
    store_entry_data(hass, entry)

    collection = resolve_profile_context_collection(hass, entry)
    assert isinstance(collection, ProfileContextCollection)
    assert collection.primary_id == "alpha"
    assert set(pid for pid, _ in collection.items()) == {"alpha", "beta"}

    primary = collection.primary
    assert primary.name == "Alpha"
    assert primary.sensor_ids_for_roles("temperature")[0] == "sensor.temp"
    assert primary.get_threshold("temperature_min") == 10

    secondary = collection.get("beta")
    assert secondary is not None
    assert secondary.name == "Beta"


@pytest.mark.asyncio
async def test_resolve_profile_context_collection_fallbacks_to_primary(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "gamma", CONF_PLANT_NAME: "Gamma"},
        options={"sensors": {"temperature": "sensor.temp"}},
    )

    collection = resolve_profile_context_collection(hass, entry)
    assert isinstance(collection, ProfileContextCollection)
    assert collection.primary_id == "gamma"

    primary = collection.primary
    assert primary.id == "gamma"
    assert primary.name == "Gamma"
    assert primary.first_sensor("temperature") == "sensor.temp"


def test_serialise_device_info_converts_sets():
    info = {
        "identifiers": {(DOMAIN, "entry:alpha")},
        "connections": {("mac", "00:11:22:33")},
        "manufacturer": "Horticulture Assistant",
        "name": "Alpha",
        "via_device": (DOMAIN, "entry:parent"),
    }

    serialised = serialise_device_info(info)

    assert serialised["identifiers"] == [[DOMAIN, "entry:alpha"]]
    assert serialised["connections"] == [["mac", "00:11:22:33"]]
    assert serialised["via_device"] == {"domain": DOMAIN, "id": "entry:parent"}
    assert serialised["name"] == "Alpha"


def test_serialise_device_info_handles_none():
    assert serialise_device_info(None) == {}
