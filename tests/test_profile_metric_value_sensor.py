import asyncio
import inspect
from collections import defaultdict

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import (
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PROFILES,
    DOMAIN,
    signal_profile_contexts_updated,
)
from custom_components.horticulture_assistant.derived import PlantPPFDSensor, PlantVPDSensor
from custom_components.horticulture_assistant.irrigation_bridge import PlantIrrigationRecommendationSensor
from custom_components.horticulture_assistant.sensor import (
    PlantStatusSensor,
    ProfileMetricValueSensor,
    async_setup_entry,
)
from custom_components.horticulture_assistant.utils.entry_helpers import (
    ensure_profile_device_registered,
    get_entry_data,
    resolve_profile_context_collection,
    store_entry_data,
)


class _DummyCoordinator:
    def __init__(self, hass):
        self.hass = hass
        self.data = {}
        self.last_update_success = True
        self.last_exception = None
        self.last_exception_msg = None
        self.latency_ms = None

    def async_add_listener(self, _callback):  # pragma: no cover - simple stub
        return lambda: None

    def async_request_refresh(self):  # pragma: no cover - simple stub
        return None


@pytest.mark.asyncio
async def test_profile_metric_value_sensor_initialises_from_context(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-1",
            CONF_PLANT_NAME: "Fern",
        },
        options={
            CONF_PROFILES: {
                "plant-1": {
                    "name": "Fern",
                    "resolved_targets": {"temperature_min": {"value": 18.5, "unit": "°C"}},
                    "targets": {"humidity_max": {"target": 70, "unit": "%"}},
                    "variables": {
                        "moisture": {"current": 30},
                    },
                }
            },
        },
    )
    entry.entry_id = "entry-1"

    await store_entry_data(hass, entry)

    collection = resolve_profile_context_collection(hass, entry)
    context = collection.contexts["plant-1"]
    meta = context.metric("resolved_targets", "temperature_min")

    sensor = ProfileMetricValueSensor(
        hass,
        entry,
        context,
        "resolved_targets",
        "temperature_min",
        meta,
    )
    sensor.hass = hass

    assert sensor.unique_id == f"{DOMAIN}_{entry.entry_id}_plant-1_resolved_targets_temperature_min"
    assert sensor.name == "Resolved Target Temperature Min"
    assert sensor.native_value == pytest.approx(18.5)
    assert sensor.native_unit_of_measurement == "°C"
    assert sensor._attr_available is True
    attrs = sensor.extra_state_attributes
    assert attrs["category"] == "resolved_targets"
    assert attrs["metric_key"] == "temperature_min"
    assert attrs["unit"] == "°C"


@pytest.mark.asyncio
async def test_profile_metric_value_sensor_device_info_anchors_to_profile_device(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-device",
            CONF_PLANT_NAME: "Orchid",
        },
        options={
            CONF_PROFILES: {
                "plant-device": {
                    "name": "Orchid",
                    "resolved_targets": {"temperature": {"value": 19.5, "unit": "°C"}},
                }
            }
        },
    )
    entry.entry_id = "entry-device"
    entry.async_on_unload = lambda func: None

    await store_entry_data(hass, entry)
    stored = get_entry_data(hass, entry)
    stored["coordinator_ai"] = _DummyCoordinator(hass)
    stored["coordinator_local"] = _DummyCoordinator(hass)
    stored.setdefault("keep_stale", True)

    added: list[ProfileMetricValueSensor] = []
    pending: list[asyncio.Task] = []

    def _add_entities(entities, update=False):
        for entity in entities:
            entity.hass = hass
            if isinstance(entity, ProfileMetricValueSensor):
                result = entity.async_added_to_hass()
                if inspect.isawaitable(result):
                    pending.append(asyncio.create_task(result))
                added.append(entity)

    await async_setup_entry(hass, entry, _add_entities)

    if pending:
        await asyncio.gather(*pending)

    assert added, "expected at least one profile metric sensor"

    expected_identifier = (DOMAIN, f"{entry.entry_id}:profile:{entry.data[CONF_PLANT_ID]}")
    expected_via = (DOMAIN, f"entry:{entry.entry_id}")

    for sensor in added:
        device_info = sensor.device_info
        assert isinstance(device_info, dict)
        identifiers = device_info.get("identifiers")
        assert isinstance(identifiers, set)
        assert expected_identifier in identifiers
        assert device_info.get("via_device") == expected_via


@pytest.mark.asyncio
async def test_profile_metric_value_sensor_refreshes_on_context_update(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-2",
            CONF_PLANT_NAME: "Basil",
        },
        options={
            CONF_PROFILES: {
                "plant-2": {
                    "name": "Basil",
                    "resolved_targets": {"temperature_min": {"value": 20, "unit": "°C"}},
                }
            }
        },
    )
    entry.entry_id = "entry-2"

    await store_entry_data(hass, entry)

    collection = resolve_profile_context_collection(hass, entry)
    context = collection.contexts["plant-2"]
    meta = context.metric("resolved_targets", "temperature_min")

    sensor = ProfileMetricValueSensor(
        hass,
        entry,
        context,
        "resolved_targets",
        "temperature_min",
        meta,
    )
    sensor.hass = hass

    assert sensor.native_value == pytest.approx(20)
    assert sensor._attr_available is True

    stored = get_entry_data(hass, entry)
    context_payload = dict(stored["profile_contexts"]["plant-2"])
    payload = dict(context_payload.get("payload", {}))
    payload["resolved_targets"] = {"temperature_min": {"value": 22, "unit": "°C"}}
    context_payload["payload"] = payload
    context_payload.pop("metrics", None)
    stored["profile_contexts"]["plant-2"] = context_payload

    sensor._refresh_from_context()

    assert sensor.native_value == pytest.approx(22)
    assert sensor.native_unit_of_measurement == "°C"
    assert sensor._attr_available is True

    payload.pop("resolved_targets", None)
    context_payload["payload"] = payload
    context_payload["thresholds"] = {}
    context_payload.pop("metrics", None)
    stored["profile_contexts"]["plant-2"] = context_payload

    sensor._refresh_from_context()

    assert sensor.native_value is None
    assert sensor._attr_available is False


@pytest.mark.asyncio
async def test_profile_metric_value_sensor_listens_for_context_dispatch(hass, monkeypatch):
    callbacks: list = []

    def _capture_dispatcher(_hass, _signal, callback):
        callbacks.append(callback)

        def _remove():
            if callback in callbacks:
                callbacks.remove(callback)

        return _remove

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.entity_base.async_dispatcher_connect",
        _capture_dispatcher,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-dispatch",
            CONF_PLANT_NAME: "Fern",
        },
        options={
            CONF_PROFILES: {
                "plant-dispatch": {
                    "name": "Fern",
                    "resolved_targets": {"temperature_min": {"value": 18.5, "unit": "°C"}},
                }
            }
        },
    )
    entry.entry_id = "entry-dispatch"

    await store_entry_data(hass, entry)

    collection = resolve_profile_context_collection(hass, entry)
    context = collection.contexts["plant-dispatch"]
    meta = context.metric("resolved_targets", "temperature_min")

    sensor = ProfileMetricValueSensor(
        hass,
        entry,
        context,
        "resolved_targets",
        "temperature_min",
        meta,
    )
    sensor.hass = hass

    recorded: list[tuple[float | None, bool, str | None]] = []

    def _record_state(*_args, **_kwargs):
        recorded.append(
            (
                sensor.native_value,
                sensor._attr_available,
                sensor.native_unit_of_measurement,
            )
        )

    sensor.async_write_ha_state = _record_state  # type: ignore[assignment]

    await sensor.async_added_to_hass()

    assert callbacks, "dispatcher callback should be registered"
    callback = callbacks[0]

    stored = get_entry_data(hass, entry)
    context_payload = dict(stored["profile_contexts"]["plant-dispatch"])
    payload = dict(context_payload.get("payload", {}))
    payload["resolved_targets"] = {"temperature_min": {"value": 21.0, "unit": "°C"}}
    context_payload["payload"] = payload
    context_payload.pop("metrics", None)
    stored["profile_contexts"]["plant-dispatch"] = context_payload

    callback({"updated": ("other-profile",)})

    assert not recorded, "unrelated updates should be ignored"

    callback({"updated": ("plant-dispatch",)})

    assert recorded[-1][0] == pytest.approx(21.0)
    assert recorded[-1][1] is True
    assert recorded[-1][2] == "°C"

    recorded.clear()

    callback({"removed": ("plant-dispatch",)})

    assert recorded[-1][0] is None
    assert recorded[-1][1] is False
    assert recorded[-1][2] is None


@pytest.mark.asyncio
async def test_ppfd_sensor_resubscribes_on_context_update(hass, monkeypatch):
    callbacks: list = []

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks.append(callback)

        def _remove():
            if callback in callbacks:
                callbacks.remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.entity_base.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-ppfd",
            CONF_PLANT_NAME: "Fern",
        },
        options={
            CONF_PROFILES: {
                "plant-ppfd": {
                    "name": "Fern",
                    "sensors": {"illuminance": ["sensor.light_old"]},
                }
            },
        },
    )
    entry.entry_id = "entry-ppfd"

    await store_entry_data(hass, entry)

    collection = resolve_profile_context_collection(hass, entry)
    context = collection.contexts["plant-ppfd"]

    subscribe_calls: list[tuple[str, ...]] = []
    cancel_calls: list[tuple[str, ...]] = []

    def fake_track(_hass, entity_ids, action):
        subscribe_calls.append(tuple(entity_ids))

        def _cancel():
            cancel_calls.append(tuple(entity_ids))
            return None

        return _cancel

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.derived.async_track_state_change_event",
        fake_track,
    )

    sensor = PlantPPFDSensor(hass, entry, context)
    sensor.hass = hass

    await sensor.async_added_to_hass()

    assert subscribe_calls == [("sensor.light_old",)]
    assert cancel_calls == []
    assert sensor._light_sensor == "sensor.light_old"

    entry.options = {
        CONF_PROFILES: {
            "plant-ppfd": {
                "name": "Fern",
                "sensors": {"illuminance": ["sensor.light_new"]},
            }
        }
    }

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-ppfd",
        entry.options[CONF_PROFILES]["plant-ppfd"],
    )
    await hass.async_block_till_done()

    updated_context = resolve_profile_context_collection(hass, entry).contexts["plant-ppfd"]
    assert updated_context.first_sensor("illuminance") == "sensor.light_new"
    assert len(subscribe_calls) >= 2
    assert subscribe_calls[-1] == ("sensor.light_new",)
    assert ("sensor.light_old",) in cancel_calls
    assert sensor._light_sensor == "sensor.light_new"


@pytest.mark.asyncio
async def test_vpd_sensor_tracks_new_temperature_humidity_sources(hass, monkeypatch):
    callbacks: list = []

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks.append(callback)

        def _remove():
            if callback in callbacks:
                callbacks.remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.entity_base.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-vpd",
            CONF_PLANT_NAME: "Basil",
        },
        options={
            CONF_PROFILES: {
                "plant-vpd": {
                    "name": "Basil",
                    "sensors": {
                        "temperature": ["sensor.temp_old"],
                        "humidity": ["sensor.hum_old"],
                    },
                }
            },
        },
    )
    entry.entry_id = "entry-vpd"

    await store_entry_data(hass, entry)
    context = resolve_profile_context_collection(hass, entry).contexts["plant-vpd"]

    subscribe_calls: list[tuple[str, ...]] = []
    cancel_calls: list[tuple[str, ...]] = []

    def fake_track(_hass, entity_ids, action):
        subscribe_calls.append(tuple(entity_ids))

        def _cancel():
            cancel_calls.append(tuple(entity_ids))
            return None

        return _cancel

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.derived.async_track_state_change_event",
        fake_track,
    )

    sensor = PlantVPDSensor(hass, entry, context)
    sensor.hass = hass
    await sensor.async_added_to_hass()

    assert subscribe_calls == [("sensor.temp_old", "sensor.hum_old")]

    entry.options = {
        CONF_PROFILES: {
            "plant-vpd": {
                "name": "Basil",
                "sensors": {
                    "temperature": ["sensor.temp_new"],
                    "humidity": ["sensor.hum_new"],
                },
            }
        }
    }

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-vpd",
        entry.options[CONF_PROFILES]["plant-vpd"],
    )
    await hass.async_block_till_done()

    updated_context = resolve_profile_context_collection(hass, entry).contexts["plant-vpd"]
    assert updated_context.first_sensor("temperature") == "sensor.temp_new"
    assert updated_context.first_sensor("humidity") == "sensor.hum_new"
    assert len(subscribe_calls) >= 2
    assert ("sensor.temp_old", "sensor.hum_old") in cancel_calls
    assert subscribe_calls[-1] == ("sensor.temp_new", "sensor.hum_new")


@pytest.mark.asyncio
async def test_irrigation_sensor_updates_source_on_context_change(hass, monkeypatch):
    callbacks: list = []

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks.append(callback)

        def _remove():
            if callback in callbacks:
                callbacks.remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.entity_base.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-irrigation",
            CONF_PLANT_NAME: "Mint",
        },
        options={
            CONF_PROFILES: {
                "plant-irrigation": {
                    "name": "Mint",
                    "sensors": {"smart_irrigation": ["sensor.irrigation_old"]},
                }
            },
        },
    )
    entry.entry_id = "entry-irrigation"

    await store_entry_data(hass, entry)
    context = resolve_profile_context_collection(hass, entry).contexts["plant-irrigation"]

    subscribe_calls: list[tuple[str, ...]] = []
    cancel_calls: list[tuple[str, ...]] = []

    def fake_track(_hass, entity_ids, action):
        subscribe_calls.append(tuple(entity_ids))

        def _cancel():
            cancel_calls.append(tuple(entity_ids))
            return None

        return _cancel

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.irrigation_bridge.async_track_state_change_event",
        fake_track,
    )

    sensor = PlantIrrigationRecommendationSensor(hass, entry, context)
    sensor.hass = hass
    await sensor.async_added_to_hass()

    assert subscribe_calls == [("sensor.irrigation_old",)]
    assert sensor._src == "sensor.irrigation_old"

    entry.options = {
        CONF_PROFILES: {
            "plant-irrigation": {
                "name": "Mint",
                "sensors": {"smart_irrigation": ["sensor.irrigation_new"]},
            }
        }
    }

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-irrigation",
        entry.options[CONF_PROFILES]["plant-irrigation"],
    )
    await hass.async_block_till_done()

    updated_context = resolve_profile_context_collection(hass, entry).contexts["plant-irrigation"]
    assert updated_context.first_sensor("smart_irrigation") == "sensor.irrigation_new"
    assert len(subscribe_calls) >= 2
    assert subscribe_calls[-1] == ("sensor.irrigation_new",)
    assert ("sensor.irrigation_old",) in cancel_calls
    assert sensor._src == "sensor.irrigation_new"


@pytest.mark.asyncio
async def test_plant_status_sensor_refreshes_monitor_on_context_update(hass, monkeypatch):
    callbacks: list = []

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks.append(callback)

        def _remove():
            if callback in callbacks:
                callbacks.remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.entity_base.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-status",
            CONF_PLANT_NAME: "Orchid",
        },
        options={
            CONF_PROFILES: {
                "plant-status": {
                    "name": "Orchid",
                    "sensors": {"temperature": ["sensor.temp"]},
                }
            },
        },
    )
    entry.entry_id = "entry-status"

    await store_entry_data(hass, entry)
    context = resolve_profile_context_collection(hass, entry).contexts["plant-status"]

    sensor = PlantStatusSensor(hass, entry, context)
    sensor.hass = hass
    await sensor.async_added_to_hass()

    original_monitor = sensor._monitor
    assert original_monitor is not None

    entry.options = {
        CONF_PROFILES: {
            "plant-status": {
                "name": "Orchid",
                "sensors": {
                    "temperature": ["sensor.temp"],
                    "humidity": ["sensor.hum"],
                },
            }
        }
    }

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-status",
        entry.options[CONF_PROFILES]["plant-status"],
    )
    await hass.async_block_till_done()

    assert sensor._monitor is not None
    assert sensor._monitor is not original_monitor


@pytest.mark.asyncio
async def test_profile_metric_value_sensor_marks_unavailable_when_context_removed(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-root",
            CONF_PLANT_NAME: "Fern",
        },
        options={
            CONF_PROFILES: {
                "plant-root": {
                    "name": "Fern",
                    "resolved_targets": {"temperature": {"value": 21, "unit": "C"}},
                }
            }
        },
    )
    entry.entry_id = "entry-unavailable"

    await store_entry_data(hass, entry)

    await ensure_profile_device_registered(
        hass,
        entry,
        "profile-missing",
        {
            "name": "Mint",
            "resolved_targets": {"temperature": {"value": 24, "unit": "°C"}},
        },
    )

    collection = resolve_profile_context_collection(hass, entry)
    context = collection.contexts["profile-missing"]
    meta = context.metric("resolved_targets", "temperature")

    sensor = ProfileMetricValueSensor(
        hass,
        entry,
        context,
        "resolved_targets",
        "temperature",
        meta,
    )
    sensor.hass = hass

    assert sensor._attr_available is True

    stored = get_entry_data(hass, entry)
    stored_contexts = stored.get("profile_contexts", {})
    stored_profiles = stored.get("profiles", {})
    stored_contexts.pop("profile-missing", None)
    stored_profiles.pop("profile-missing", None)
    snapshot = stored.get("snapshot")
    if isinstance(snapshot, dict):
        profiles = snapshot.get("profiles")
        if isinstance(profiles, dict):
            profiles.pop("profile-missing", None)

    sensor._refresh_from_context()

    assert sensor.native_value is None
    assert sensor._attr_available is False


@pytest.mark.asyncio
async def test_sensor_setup_entry_creates_profile_metric_entities(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-setup",
            CONF_PLANT_NAME: "Fern",
        },
        options={
            CONF_PROFILES: {
                "plant-setup": {
                    "name": "Fern",
                    "resolved_targets": {
                        "temperature": {"value": 21, "unit": "°C"},
                        "ph": {"min": 5.5, "max": 6.2},
                    },
                    "targets": {"humidity": {"target": 65, "unit": "%"}},
                    "variables": {"moisture": {"current": 40}},
                    "thresholds": {"temperature": 18},
                }
            }
        },
    )
    entry.entry_id = "entry-setup"
    entry.async_on_unload = lambda func: None

    await store_entry_data(hass, entry)
    stored = get_entry_data(hass, entry)
    stored["coordinator_ai"] = _DummyCoordinator(hass)
    stored["coordinator_local"] = _DummyCoordinator(hass)
    stored["coordinator"] = _DummyCoordinator(hass)
    stored.setdefault("keep_stale", True)

    added = []
    pending: list[asyncio.Task] = []

    def _add_entities(entities, update=False):
        for entity in entities:
            entity.hass = hass
            added.append(entity)
            if isinstance(entity, ProfileMetricValueSensor):
                result = entity.async_added_to_hass()
                if inspect.isawaitable(result):
                    pending.append(asyncio.create_task(result))

    await async_setup_entry(hass, entry, _add_entities)

    if pending:
        await asyncio.gather(*pending)

    metric_entities = [entity for entity in added if isinstance(entity, ProfileMetricValueSensor)]
    unique_ids = {entity.unique_id for entity in metric_entities}
    base = f"{DOMAIN}_{entry.entry_id}_{entry.data[CONF_PLANT_ID]}"

    assert f"{base}_resolved_targets_temperature" in unique_ids
    assert f"{base}_targets_humidity" in unique_ids
    assert f"{base}_variables_moisture" in unique_ids
    assert f"{base}_thresholds_temperature" in unique_ids
    assert f"{base}_resolved_targets_ph_min" in unique_ids
    assert f"{base}_resolved_targets_ph_max" in unique_ids


@pytest.mark.asyncio
async def test_sensor_creates_metric_entities_for_added_profiles(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-base",
            CONF_PLANT_NAME: "Basil",
        },
        options={
            CONF_PROFILES: {
                "plant-base": {
                    "name": "Basil",
                    "resolved_targets": {"temperature": {"value": 20, "unit": "°C"}},
                    "variables": {"moisture": {"current": 30}},
                }
            }
        },
    )
    entry.entry_id = "entry-update"
    entry.async_on_unload = lambda func: None

    await store_entry_data(hass, entry)
    stored = get_entry_data(hass, entry)
    stored["coordinator_ai"] = _DummyCoordinator(hass)
    stored["coordinator_local"] = _DummyCoordinator(hass)
    stored["coordinator"] = _DummyCoordinator(hass)
    stored.setdefault("keep_stale", True)

    callbacks: dict[str, list] = defaultdict(list)

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks[signal].append(callback)

        def _remove():
            if callback in callbacks[signal]:
                callbacks[signal].remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks.get(signal, [])):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.sensor.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    added = []
    pending: list[asyncio.Task] = []

    def _add_entities(entities, update=False):
        for entity in entities:
            entity.hass = hass
            added.append(entity)
            if isinstance(entity, ProfileMetricValueSensor):
                result = entity.async_added_to_hass()
                if inspect.isawaitable(result):
                    pending.append(asyncio.create_task(result))

    await async_setup_entry(hass, entry, _add_entities)

    if pending:
        await asyncio.gather(*pending)

    initial_metric_ids = {entity.unique_id for entity in added if isinstance(entity, ProfileMetricValueSensor)}

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-added",
        {
            "general": {"name": "Mint"},
            "resolved_targets": {"temperature": {"value": 24, "unit": "°C"}},
            "variables": {"moisture": {"current": 55}},
            "thresholds": {"temperature": 19},
        },
    )

    signal = signal_profile_contexts_updated(entry.entry_id)
    assert callbacks[signal]

    new_metric_ids = {entity.unique_id for entity in added if isinstance(entity, ProfileMetricValueSensor)}

    added_ids = new_metric_ids - initial_metric_ids
    assert any(uid.endswith("_plant-added_variables_moisture") for uid in added_ids)
    assert any(uid.endswith("_plant-added_resolved_targets_temperature") for uid in added_ids)
    assert any(uid.endswith("_plant-added_thresholds_temperature") for uid in added_ids)


@pytest.mark.asyncio
async def test_sensor_creates_metric_entities_for_profile_updates(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-base",
            CONF_PLANT_NAME: "Basil",
        },
        options={
            CONF_PROFILES: {
                "plant-base": {
                    "name": "Basil",
                    "resolved_targets": {"temperature": {"value": 20, "unit": "°C"}},
                }
            }
        },
    )
    entry.entry_id = "entry-update-existing"
    entry.async_on_unload = lambda func: None

    await store_entry_data(hass, entry)
    stored = get_entry_data(hass, entry)
    stored["coordinator_ai"] = _DummyCoordinator(hass)
    stored["coordinator_local"] = _DummyCoordinator(hass)
    stored["coordinator"] = _DummyCoordinator(hass)
    stored.setdefault("keep_stale", True)

    callbacks: dict[str, list] = defaultdict(list)

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks[signal].append(callback)

        def _remove():
            if callback in callbacks[signal]:
                callbacks[signal].remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks.get(signal, [])):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.sensor.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    added = []
    pending: list[asyncio.Task] = []

    def _add_entities(entities, update=False):
        for entity in entities:
            entity.hass = hass
            added.append(entity)
            if isinstance(entity, ProfileMetricValueSensor):
                result = entity.async_added_to_hass()
                if inspect.isawaitable(result):
                    pending.append(asyncio.create_task(result))

    await async_setup_entry(hass, entry, _add_entities)

    if pending:
        await asyncio.gather(*pending)

    initial_metric_ids = {entity.unique_id for entity in added if isinstance(entity, ProfileMetricValueSensor)}

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-base",
        {
            "resolved_targets": {"temperature": {"value": 21, "unit": "°C"}},
            "variables": {"moisture": {"current": 40}},
        },
    )

    signal = signal_profile_contexts_updated(entry.entry_id)
    assert callbacks[signal]

    if pending:
        await asyncio.gather(*pending)

    updated_metric_ids = {entity.unique_id for entity in added if isinstance(entity, ProfileMetricValueSensor)}
    new_metric_ids = updated_metric_ids - initial_metric_ids

    assert any(uid.endswith("_plant-base_variables_moisture") for uid in new_metric_ids)


@pytest.mark.asyncio
async def test_sensor_adds_context_entities_for_profile_updates(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "plant-base",
            CONF_PLANT_NAME: "Basil",
        },
        options={
            CONF_PROFILES: {
                "plant-base": {
                    "name": "Basil",
                    "sensors": {"temperature": ["sensor.temperature"]},
                }
            }
        },
    )
    entry.entry_id = "entry-context-update"
    entry.async_on_unload = lambda func: None

    await store_entry_data(hass, entry)
    stored = get_entry_data(hass, entry)
    stored["coordinator_ai"] = _DummyCoordinator(hass)
    stored["coordinator_local"] = _DummyCoordinator(hass)
    stored["coordinator"] = _DummyCoordinator(hass)
    stored.setdefault("keep_stale", True)

    callbacks: dict[str, list] = defaultdict(list)

    def _capture_dispatcher_connect(_hass, signal, callback):
        callbacks[signal].append(callback)

        def _remove():
            if callback in callbacks[signal]:
                callbacks[signal].remove(callback)

        return _remove

    def _emit_dispatch(_hass, signal, payload):
        for registered in tuple(callbacks.get(signal, [])):
            registered(payload)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.sensor.async_dispatcher_connect",
        _capture_dispatcher_connect,
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.entry_helpers.async_dispatcher_send",
        _emit_dispatch,
    )

    added: list = []
    pending: list[asyncio.Task] = []

    def _add_entities(entities, update=False):
        for entity in entities:
            entity.hass = hass
            added.append(entity)
            if isinstance(entity, ProfileMetricValueSensor):
                result = entity.async_added_to_hass()
                if inspect.isawaitable(result):
                    pending.append(asyncio.create_task(result))

    await async_setup_entry(hass, entry, _add_entities)

    if pending:
        await asyncio.gather(*pending)
        pending.clear()

    base = f"{DOMAIN}_{entry.entry_id}_{entry.data[CONF_PLANT_ID]}"
    initial_context_ids = {entity.unique_id for entity in added if not isinstance(entity, ProfileMetricValueSensor)}
    assert f"{base}_vpd" not in initial_context_ids
    assert f"{base}_dew_point" not in initial_context_ids
    assert f"{base}_mold_risk" not in initial_context_ids

    await ensure_profile_device_registered(
        hass,
        entry,
        "plant-base",
        {
            "name": "Basil",
            "sensors": {
                "temperature": ["sensor.temperature"],
                "humidity": ["sensor.humidity"],
            },
        },
    )

    signal = signal_profile_contexts_updated(entry.entry_id)
    assert callbacks[signal]

    if pending:
        await asyncio.gather(*pending)
        pending.clear()

    updated_context_ids = {entity.unique_id for entity in added if not isinstance(entity, ProfileMetricValueSensor)}
    added_context_ids = updated_context_ids - initial_context_ids

    assert f"{base}_vpd" in added_context_ids
    assert f"{base}_dew_point" in added_context_ids
    assert f"{base}_mold_risk" in added_context_ids
