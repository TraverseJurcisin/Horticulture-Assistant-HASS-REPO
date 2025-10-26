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
    build_entry_snapshot,
    get_entry_plant_info,
    get_primary_profile_id,
    get_primary_profile_sensors,
    get_primary_profile_thresholds,
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
    entry.options = {CONF_PROFILES: {"new": {"name": "New"}}}
    entry.data = {CONF_PLANT_ID: "new", "plant_name": "New"}
    refreshed = update_entry_data(hass, entry)
    assert refreshed["plant_id"] == "new"
    assert hass.data[DOMAIN][BY_PLANT_ID]["new"] is refreshed
    assert "old" not in hass.data[DOMAIN][BY_PLANT_ID]
