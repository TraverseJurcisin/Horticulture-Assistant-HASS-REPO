from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

from custom_components.horticulture_assistant.const import signal_profile_contexts_updated
from custom_components.horticulture_assistant.utils.entry_helpers import (
    ProfileContext,
    _resolve_profile_metrics,
    ensure_all_profile_devices_registered,
    ensure_profile_device_registered,
    get_entry_data,
    get_entry_data_by_plant_id,
    get_entry_plant_info,
    remove_entry_data,
    store_entry_data,
)


class DummyEntry(SimpleNamespace):
    def __init__(self, **kwargs):
        kwargs.setdefault("options", {})
        super().__init__(**kwargs)


def test_profile_context_metric_helpers():
    context = ProfileContext(
        id="plant-1",
        name="Plant",
        metrics={
            "variables": {
                "moisture": {"value": 32, "unit": "%", "raw": {"current": 32}},
            }
        },
    )

    assert context.metric_value("variables", "moisture") == 32
    metric = context.metric("variables", "moisture")
    assert isinstance(metric, Mapping)
    assert metric["unit"] == "%"
    assert context.metric_value("variables", "unknown", default=5) == 5


def test_get_entry_plant_info_defaults():
    entry = DummyEntry(entry_id="eid", data={})
    pid, name = get_entry_plant_info(entry)
    assert pid == "eid"
    assert name.startswith("Plant ")


def test_get_entry_plant_info_explicit():
    entry = DummyEntry(entry_id="eid", data={"plant_id": "pid1", "plant_name": "Tom"})
    pid, name = get_entry_plant_info(entry)
    assert pid == "pid1"
    assert name == "Tom"


class DummyHass(SimpleNamespace):
    def __init__(self, base: str):
        super().__init__(config=SimpleNamespace(path=lambda n: f"{base}/{n}"))
        self.data = {}


@pytest.mark.asyncio
async def test_store_and_remove_entry_data(tmp_path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="e1", data={"plant_name": "Tomato"})
    stored = await store_entry_data(hass, entry)
    assert hass.data
    assert hass.data["horticulture_assistant"]["e1"] is stored
    assert stored["profile_dir"] == Path(tmp_path / "plants/e1")
    assert get_entry_data(hass, "e1") is stored
    assert get_entry_data(hass, entry) is stored
    assert get_entry_data_by_plant_id(hass, "e1") is stored
    remove_entry_data(hass, "e1")
    assert "horticulture_assistant" not in hass.data or "e1" not in hass.data["horticulture_assistant"]
    assert get_entry_data(hass, "e1") is None
    assert get_entry_data_by_plant_id(hass, "e1") is None


@pytest.mark.asyncio
async def test_get_entry_data_by_plant_id(tmp_path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="e99", data={"plant_id": "pid99", "plant_name": "Pepper"})
    stored = await store_entry_data(hass, entry)
    assert get_entry_data_by_plant_id(hass, "pid99") is stored


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_dispatch(tmp_path, monkeypatch):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="entry1", data={"plant_id": "plant1", "plant_name": "Plant"})
    entry.options = {"profiles": {}}

    await store_entry_data(hass, entry)

    calls = []

    def _record_dispatch(_hass, signal, payload):
        calls.append((signal, payload))

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _record_dispatch,
    )

    await ensure_profile_device_registered(
        hass,
        entry,
        "new_profile",
        {"general": {"name": "New Profile"}},
    )

    stored = get_entry_data(hass, entry)
    assert "new_profile" in stored.get("profile_contexts", {})

    signal = signal_profile_contexts_updated(entry.entry_id)
    matching = [payload for sent, payload in calls if sent == signal]
    assert matching
    payload = matching[-1]
    assert payload.get("added") == ("new_profile",)
    assert payload.get("removed") == ()
    assert payload.get("updated") == ()


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_dispatch_on_update(tmp_path, monkeypatch):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="entry1", data={"plant_id": "plant1", "plant_name": "Plant"})
    entry.options = {"profiles": {}}

    await store_entry_data(hass, entry)

    calls = []

    def _record_dispatch(_hass, signal, payload):
        calls.append((signal, payload))

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _record_dispatch,
    )

    await ensure_profile_device_registered(
        hass,
        entry,
        "profile-up",
        {"general": {"name": "Profile"}, "variables": {"humidity": {"current": 50}}},
    )

    calls.clear()

    await ensure_profile_device_registered(
        hass,
        entry,
        "profile-up",
        {"general": {"name": "Profile"}, "variables": {"humidity": {"current": 55}}},
    )

    signal = signal_profile_contexts_updated(entry.entry_id)
    matching = [payload for sent, payload in calls if sent == signal]
    assert matching
    payload = matching[-1]
    assert payload.get("added") == ()
    assert payload.get("removed") == ()
    assert payload.get("updated") == ("profile-up",)


@pytest.mark.asyncio
async def test_ensure_all_profile_devices_registered_delays_dispatch(tmp_path, monkeypatch):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="entry2", data={"plant_id": "plant1", "plant_name": "Plant"})
    entry.options = {"profiles": {"existing": {"name": "Existing"}}}

    await store_entry_data(hass, entry)

    profiles = dict(entry.options.get("profiles", {}))
    profiles["new_profile"] = {
        "name": "New Profile",
        "sensors": {"moisture": "sensor.moisture"},
    }
    entry.options["profiles"] = profiles

    calls = []

    def _record_dispatch(_hass, signal, payload):
        calls.append((signal, payload))

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _record_dispatch,
    )

    await ensure_all_profile_devices_registered(hass, entry)

    stored = get_entry_data(hass, entry)
    contexts = stored.get("profile_contexts", {}) if isinstance(stored, dict) else {}
    assert "new_profile" in contexts

    signal = signal_profile_contexts_updated(entry.entry_id)
    assert any(signal == sent and payload.get("added") == ("new_profile",) for sent, payload in calls)


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_merges_threshold_sources(tmp_path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry(entry_id="entry3", data={"plant_id": "plant3", "plant_name": "Plant"})
    entry.options = {}

    await store_entry_data(hass, entry)

    payload = {
        "resolved_targets": {"temperature_min": {"value": 18.5}},
        "targets": {"humidity_max": {"target": 70}},
        "variables": {
            "moisture_min": {"current": 30},
            "lux_to_ppfd": 0.5,
        },
    }

    await ensure_profile_device_registered(
        hass,
        entry,
        "profile-3",
        payload,
    )

    stored = get_entry_data(hass, entry)
    context = stored.get("profile_contexts", {}).get("profile-3", {})
    thresholds = context.get("thresholds", {})

    assert thresholds["temperature_min"] == pytest.approx(18.5)
    assert thresholds["humidity_max"] == 70
    assert thresholds["moisture_min"] == 30
    assert thresholds["lux_to_ppfd"] == pytest.approx(0.5)

    metrics = context.get("metrics", {})
    resolved = metrics.get("resolved_targets", {})
    targets = metrics.get("targets", {})
    variables = metrics.get("variables", {})
    threshold_metrics = metrics.get("thresholds", {})

    assert resolved["temperature_min"]["value"] == pytest.approx(18.5)
    assert targets["humidity_max"]["value"] == 70
    assert variables["moisture_min"]["value"] == 30
    assert variables["lux_to_ppfd"]["value"] == pytest.approx(0.5)
    assert threshold_metrics["temperature_min"]["value"] == pytest.approx(18.5)
    assert threshold_metrics["humidity_max"]["value"] == 70
    assert threshold_metrics["moisture_min"]["value"] == 30
    assert threshold_metrics["lux_to_ppfd"]["value"] == pytest.approx(0.5)


def test_resolve_profile_metrics_expands_range_values():
    payload = {
        "targets": {
            "temperature": {
                "min": {"value": 18, "unit": "°C"},
                "max": {"value": 26, "unit": "°C"},
                "unit": "°C",
            }
        },
        "variables": {
            "humidity": {"low": {"value": 45}, "high": {"value": 65}},
        },
    }

    metrics = _resolve_profile_metrics(payload)

    temp_metrics = metrics.get("targets", {})
    assert temp_metrics["temperature_min"]["value"] == 18
    assert temp_metrics["temperature_max"]["value"] == 26
    assert temp_metrics["temperature_min"]["unit"] == "°C"
    assert temp_metrics["temperature_max"]["unit"] == "°C"

    humidity_metrics = metrics.get("variables", {})
    assert humidity_metrics["humidity_min"]["value"] == 45
    assert humidity_metrics["humidity_max"]["value"] == 65
