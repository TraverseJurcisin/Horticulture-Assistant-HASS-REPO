"""Tests for helper utilities that derive profile defaults from entries."""

from __future__ import annotations

import asyncio
import types
from typing import Any, Iterable
from unittest.mock import patch

import pytest

import custom_components.horticulture_assistant.utils.entry_helpers as helpers

from custom_components.horticulture_assistant.const import (
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PROFILES,
    DOMAIN,
)
from custom_components.horticulture_assistant.utils.entry_helpers import (
    BY_PLANT_ID,
    ProfileContext,
    ProfileContextCollection,
    async_sync_entry_devices,
    backfill_profile_devices_from_options,
    build_entry_snapshot,
    build_profile_device_info,
    ensure_all_profile_devices_registered,
    ensure_profile_device_registered,
    entry_device_identifier,
    get_entry_data,
    get_entry_data_by_plant_id,
    get_entry_plant_info,
    get_primary_profile_id,
    get_primary_profile_options,
    get_primary_profile_sensors,
    get_primary_profile_thresholds,
    profile_device_identifier,
    resolve_entry_device_info,
    resolve_profile_context_collection,
    resolve_profile_device_info,
    resolve_profile_image_url,
    serialise_device_info,
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


def test_primary_profile_id_strips_whitespace():
    entry = _make_entry(data={CONF_PLANT_ID: "  gamma  "})
    assert get_primary_profile_id(entry) == "gamma"


def test_primary_profile_options_follow_canonical_identifier():
    entry = _make_entry(
        data={CONF_PLANT_ID: "  mint  "},
        options={CONF_PROFILES: {"  mint  ": {"name": "Mint"}}},
    )

    options = get_primary_profile_options(entry)

    assert options["name"] == "Mint"


def test_entry_plant_info_prefers_profile_name():
    entry = _make_entry(
        options={CONF_PROFILES: {"p1": {"name": "Rose"}}},
        data={CONF_PLANT_ID: "p1", "plant_name": "Fallback"},
    )
    assert get_entry_plant_info(entry) == ("p1", "Rose")


def test_entry_plant_info_trims_identifier():
    entry = _make_entry(
        data={CONF_PLANT_ID: "  plant-01  "},
        options={CONF_PROFILES: {"  plant-01  ": {"name": "Mint"}}},
    )
    plant_id, plant_name = get_entry_plant_info(entry)
    assert plant_id == "plant-01"
    assert plant_name == "Mint"


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


def test_entry_snapshot_normalises_profile_identifiers():
    entry = _make_entry(
        data={CONF_PLANT_ID: "  herb  ", CONF_PLANT_NAME: "Herb"},
        options={CONF_PROFILES: {"  herb  ": {"name": "Herb"}}},
    )

    snap = build_entry_snapshot(entry)

    assert snap["plant_id"] == "herb"
    assert snap["primary_profile_id"] == "herb"
    assert list(snap["profiles"].keys()) == ["herb"]


def test_primary_sensors_use_top_level_mapping():
    entry = _make_entry(options={"sensors": {"temperature": "sensor.temp"}})
    assert get_primary_profile_sensors(entry) == {"temperature": "sensor.temp"}


def test_primary_sensors_strip_whitespace():
    entry = _make_entry(options={"sensors": {"temperature": "  sensor.temp  ", "humidity": "\n"}})

    assert get_primary_profile_sensors(entry) == {"temperature": "sensor.temp"}


def test_profile_context_deduplicates_sequence_sensor_ids():
    context = ProfileContext(
        id="plant",
        name="Plant",
        sensors={"moisture": [" sensor.one ", "sensor.one", "", "sensor.two", "sensor.two"]},
    )

    assert context.sensors["moisture"] == ("sensor.one", "sensor.two")


def test_primary_sensors_accept_sequence_values():
    entry = _make_entry(options={"sensors": {"moisture": ["sensor.moist", "sensor.backup"]}})

    assert get_primary_profile_sensors(entry) == {"moisture": "sensor.moist"}


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


class _FakeDeviceRegistry:
    def __init__(self) -> None:
        self.devices: dict[str, Any] = {}
        self.update_calls: list[tuple[str, dict[str, Any]]] = []

    @staticmethod
    def _pairs(value):
        if value is None:
            return set()
        items = value if isinstance(value, list | tuple | set) else [value]
        pairs: set[tuple[str, str]] = set()
        for item in items:
            if isinstance(item, list | tuple) and len(item) == 2:
                pairs.add((str(item[0]), str(item[1])))
        return pairs

    def async_get_device(self, identifiers, *_args, **_kwargs):
        pairs = self._pairs(identifiers)
        for device in self.devices.values():
            if device.identifiers & pairs:
                return device
        return None

    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        pairs = self._pairs(identifiers)
        existing = self.async_get_device(pairs)
        if existing is not None:
            if config_entry_id:
                existing.config_entries.add(config_entry_id)
            name = kwargs.get("name")
            if name:
                existing.name = name
            for field in ("via_device", "via_device_id"):
                if field in kwargs:
                    setattr(existing, field, kwargs[field])
            return existing

        device_id = f"device_{len(self.devices)}"
        device = types.SimpleNamespace(
            id=device_id,
            identifiers=pairs,
            config_entries={config_entry_id} if config_entry_id else set(),
            name=kwargs.get("name"),
        )
        for field in ("via_device", "via_device_id"):
            setattr(device, field, kwargs.get(field))
        self.devices[device_id] = device
        return device

    def async_update_device(self, device_id, **kwargs):
        device = self.devices.get(device_id)
        if device is None:
            return None
        updates = {}
        for key, value in kwargs.items():
            updates[str(key)] = value
            setattr(device, key, value)
        self.update_calls.append((device_id, updates))
        return device


class _RejectingDeviceRegistry(_FakeDeviceRegistry):
    def __init__(
        self,
        *,
        entry_device_id: str | None,
        reject: tuple[str, ...] | list[str],
        required_profile_args: Iterable[str] | None = None,
        lookup_entry_device_id: str | None = None,
    ):
        super().__init__()
        self._entry_device_id = entry_device_id
        self._reject = {str(arg) for arg in reject}
        self._required_profile_args = (
            tuple(str(arg) for arg in required_profile_args)
            if required_profile_args
            else tuple()
        )
        self._lookup_entry_device_id = lookup_entry_device_id

    def async_get_device(self, identifiers, *_args, **_kwargs):
        device = super().async_get_device(identifiers)
        if device is None:
            return None
        if self._lookup_entry_device_id:
            pairs = self._pairs(identifiers)
            if any(":profile:" not in ident for _, ident in pairs):
                device.id = self._lookup_entry_device_id
        return device

    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        pairs = self._pairs(identifiers)
        is_profile = any(":profile:" in ident for _, ident in pairs)

        if is_profile:
            for arg in self._reject:
                if arg in kwargs:
                    raise TypeError(
                        f"async_get_or_create() got an unexpected keyword argument '{arg}'"
                    )
            for required in self._required_profile_args:
                if required not in kwargs:
                    raise TypeError(
                        f"async_get_or_create() missing required keyword argument '{required}'"
                    )

        device = super().async_get_or_create(
            identifiers=identifiers,
            config_entry_id=config_entry_id,
            **kwargs,
        )

        if not is_profile:
            device.id = self._entry_device_id

        return device


class _TupleReturningDeviceRegistry(_RejectingDeviceRegistry):
    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        device = super().async_get_or_create(
            identifiers=identifiers,
            config_entry_id=config_entry_id,
            **kwargs,
        )
        return device, False


class _MappingReturningDeviceRegistry(_RejectingDeviceRegistry):
    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        device = super().async_get_or_create(
            identifiers=identifiers,
            config_entry_id=config_entry_id,
            **kwargs,
        )
        return {"device": device, "created": False}


class _AsyncDeviceRegistry(_FakeDeviceRegistry):
    async def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        return super().async_get_or_create(
            identifiers=identifiers,
            config_entry_id=config_entry_id,
            **kwargs,
        )

    async def async_update_device(self, device_id, **kwargs):
        return super().async_update_device(device_id, **kwargs)


class _BooleanUpdatingDeviceRegistry(_RejectingDeviceRegistry):
    def async_update_device(self, device_id, **kwargs):
        device = super().async_update_device(device_id, **kwargs)
        return bool(device)


@pytest.mark.asyncio
async def test_store_entry_data_tracks_snapshot(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "p2", "plant_name": "Stored"},
        options={CONF_PROFILES: {"p2": {"name": "Stored", "sensors": {"moisture": "sensor.moist"}}}},
    )
    stored = await store_entry_data(hass, entry)
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
    await store_entry_data(hass, entry)
    entry.options = {CONF_PROFILES: {"new": {"name": "New"}, "child": {"name": "Child"}}}
    entry.data = {CONF_PLANT_ID: "new", "plant_name": "New"}
    refreshed = await update_entry_data(hass, entry)
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
            "sensors": {"moisture": ["sensor.moist"]},
            CONF_PROFILES: {"p2": {"name": "Stored", "general": {"plant_type": "herb", "area": "Kitchen"}}},
        },
    )
    stored = await store_entry_data(hass, entry)
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
async def test_async_resolve_device_registry_supports_async_get_registry(hass):
    registry = _FakeDeviceRegistry()

    class _RegistryProvider:
        def __init__(self) -> None:
            self.calls = 0

        def async_get_registry(self, hass_arg):
            self.calls += 1
            return registry

    provider = _RegistryProvider()
    original = helpers.dr
    helpers.dr = types.SimpleNamespace(async_get_registry=provider.async_get_registry)
    try:
        resolved = await helpers._async_resolve_device_registry(hass)
    finally:
        helpers.dr = original

    assert resolved is registry
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_async_resolve_device_registry_accepts_loader_result(hass):
    registry = _FakeDeviceRegistry()
    calls = {"count": 0}

    def _load_registry(_hass):
        calls["count"] += 1
        return registry

    original = helpers.dr
    helpers.dr = types.SimpleNamespace(
        async_get=lambda *_args, **_kwargs: None,
        async_load_device_registry=_load_registry,
    )
    try:
        resolved = await helpers._async_resolve_device_registry(hass)
    finally:
        helpers.dr = original

    assert resolved is registry
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_async_resolve_device_registry_retries_getter_after_loader(hass):
    registry = _FakeDeviceRegistry()
    state = {"loaded": False}

    def _async_get(_hass):
        if not state["loaded"]:
            raise RuntimeError("not ready")
        return registry

    def _async_load(_hass):
        state["loaded"] = True

    original = helpers.dr
    helpers.dr = types.SimpleNamespace(async_get=_async_get, async_load=_async_load)
    try:
        resolved = await helpers._async_resolve_device_registry(hass)
    finally:
        helpers.dr = original

    assert resolved is registry
    assert state["loaded"] is True


def test_build_profile_device_info_handles_non_mapping_general():
    payload = {"name": "Plant", "general": ["not", "a", "mapping"]}

    info = build_profile_device_info("entry", "plant", payload, snapshot=None)

    assert info["name"] == "Plant"
    assert info["model"] == "Plant Profile"
    assert profile_device_identifier("entry", "plant") in info["identifiers"]


@pytest.mark.asyncio
async def test_resolve_profile_device_info_tracks_updates(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "alpha", CONF_PLANT_NAME: "Alpha"},
        options={CONF_PROFILES: {"alpha": {"name": "Alpha"}}},
    )
    await store_entry_data(hass, entry)
    info = resolve_profile_device_info(hass, entry.entry_id, "alpha")
    assert info["name"] == "Alpha"

    entry.options = {CONF_PROFILES: {"alpha": {"name": "Renamed"}}}
    await update_entry_data(hass, entry)
    updated = resolve_profile_device_info(hass, entry.entry_id, "alpha")
    assert updated["name"] == "Renamed"


@pytest.mark.asyncio
async def test_resolve_entry_device_info_returns_metadata(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "beta", CONF_PLANT_NAME: "Beta"},
        options={CONF_PROFILES: {"beta": {"name": "Beta"}}},
    )
    await store_entry_data(hass, entry)
    info = resolve_entry_device_info(hass, entry.entry_id)
    assert info is not None
    assert entry_device_identifier(entry.entry_id) in info["identifiers"]
    assert info["name"] == "Beta"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_populates_missing_device(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _FakeDeviceRegistry()
    profile_payload = {
        "name": "Mint",
        "general": {"display_name": "Mint", "plant_type": "herb"},
    }

    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            profile_payload,
            snapshot=snapshot,
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.name == "Mint"
    assert profile_device.via_device_id == entry_device.id

    stored = get_entry_data(hass, entry)
    assert stored is not None
    assert stored["profiles"]["mint"]["name"] == "Mint"
    assert stored["profile_devices"]["mint"]["name"] == "Mint"
    assert stored["profile_contexts"]["mint"]["name"] == "Mint"
    assert stored["profile_dir"] == tmp_path / "plants" / "mint"

    mapping = hass.data[DOMAIN][BY_PLANT_ID]
    assert mapping["mint"] is stored
    assert get_entry_data_by_plant_id(hass, "mint") is stored


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_supports_async_registry(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "sage", CONF_PLANT_NAME: "Sage"},
        options={CONF_PROFILES: {}},
        entry_id="entry-sage",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _AsyncDeviceRegistry()

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "sage",
            {"name": "Sage"},
        )

    profile_identifier = profile_device_identifier(entry.entry_id, "sage")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.name == "Sage"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_recovers_without_via_device_support(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _RejectingDeviceRegistry(entry_device_id=None, reject=("via_device",))

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot={
                "plant_id": "mint",
                "plant_name": "Mint",
                "primary_profile_id": "mint",
                "primary_profile_name": "Mint",
                "profiles": {},
            },
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id is None

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.name == "Mint"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_derives_missing_parent_id(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _RejectingDeviceRegistry(
        entry_device_id=None,
        reject=("via_device",),
        required_profile_args=("via_device_id",),
        lookup_entry_device_id="entry-device",
    )

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot={
                "plant_id": "mint",
                "plant_name": "Mint",
                "primary_profile_id": "mint",
                "primary_profile_name": "Mint",
                "profiles": {},
            },
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.via_device_id == entry_device.id
    assert profile_device.name == "Mint"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_unwraps_tuple_entry_response(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _TupleReturningDeviceRegistry(
        entry_device_id="entry-device",
        reject=("via_device",),
        required_profile_args=("via_device_id",),
    )

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot={
                "plant_id": "mint",
                "plant_name": "Mint",
                "primary_profile_id": "mint",
                "primary_profile_name": "Mint",
                "profiles": {},
            },
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.via_device_id == entry_device.id
    assert profile_device.name == "Mint"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_unwraps_mapping_entry_response(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _MappingReturningDeviceRegistry(
        entry_device_id="entry-device",
        reject=("via_device",),
        required_profile_args=("via_device_id",),
    )

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot={
                "plant_id": "mint",
                "plant_name": "Mint",
                "primary_profile_id": "mint",
                "primary_profile_name": "Mint",
                "profiles": {},
            },
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.via_device_id == entry_device.id
    assert profile_device.name == "Mint"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_falls_back_to_legacy_via_device(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _RejectingDeviceRegistry(
        entry_device_id="entry-device",
        reject=("via_device_id",),
    )

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot={
                "plant_id": "mint",
                "plant_name": "Mint",
                "primary_profile_id": "mint",
                "primary_profile_name": "Mint",
                "profiles": {},
            },
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.name == "Mint"


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_links_parent_after_rejection(
    hass, tmp_path
):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _RejectingDeviceRegistry(
        entry_device_id="entry-device",
        reject=("via_device", "via_device_id"),
    )

    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot=snapshot,
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.via_device_id == entry_device.id
    assert fake_registry.update_calls
    last_update = fake_registry.update_calls[-1]
    assert last_update[1].get("via_device_id") == entry_device.id


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_refreshes_after_boolean_update(
    hass, tmp_path
):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _BooleanUpdatingDeviceRegistry(
        entry_device_id="entry-device",
        reject=("via_device", "via_device_id"),
    )

    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot=snapshot,
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.via_device_id == entry_device.id
    assert fake_registry.update_calls


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_indexes_profile_without_payload(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _FakeDeviceRegistry()
    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint-clone",
            None,
            snapshot=snapshot,
        )

    profile_identifier = profile_device_identifier(entry.entry_id, "mint-clone")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None

    stored = get_entry_data(hass, entry)
    assert stored is not None
    assert "mint-clone" in stored["profile_ids"]
    assert stored["profiles"].get("mint-clone") == {}

    mapping = hass.data[DOMAIN][BY_PLANT_ID]
    assert mapping["mint-clone"] is stored
    assert get_entry_data_by_plant_id(hass, "mint-clone") is stored


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_normalises_blank_identifier(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _FakeDeviceRegistry()
    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }

    profile_payload = {"name": "Mint Clone"}

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "   ",
            profile_payload,
            snapshot=snapshot,
        )

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.name == "Mint Clone"

    stored = get_entry_data(hass, entry)
    assert stored is not None
    assert "mint" in stored["profile_ids"]
    assert stored["profiles"]["mint"]["name"] == "Mint Clone"
    assert stored["profile_devices"]["mint"]["name"] == "Mint Clone"
    assert stored["profile_contexts"]["mint"]["name"] == "Mint Clone"
    assert "" not in stored["profiles"]


@pytest.mark.asyncio
async def test_ensure_profile_device_registered_appends_canonical_identifiers(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _FakeDeviceRegistry()
    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {"mint": {"name": "Mint"}},
    }

    with (
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
            return_value=fake_registry,
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.build_entry_device_info",
            return_value={"identifiers": {("other", "entry")}, "name": "Mint"},
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.build_profile_device_info",
            return_value={"identifiers": {("other", "profile")}, "name": "Mint"},
        ),
    ):
        await ensure_profile_device_registered(
            hass,
            entry,
            "mint",
            {"name": "Mint"},
            snapshot=snapshot,
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    profile_identifier = profile_device_identifier(entry.entry_id, "mint")

    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_identifier in entry_device.identifiers
    assert ("other", "entry") in entry_device.identifiers

    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_identifier in profile_device.identifiers
    assert ("other", "profile") in profile_device.identifiers

    stored = get_entry_data(hass, entry)
    assert stored is not None
    assert stored["entry_device_identifier"] == entry_identifier
    assert entry_identifier in stored["entry_device_info"]["identifiers"]
    assert profile_identifier in stored["profile_devices"]["mint"]["identifiers"]


@pytest.mark.asyncio
async def test_ensure_all_profile_devices_registered_registers_all_profiles(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "garden", CONF_PLANT_NAME: "Garden"},
        options={
            CONF_PROFILES: {
                "alpha": {"name": "Alpha", "general": {"display_name": "Alpha"}},
                "beta": {"name": "Beta", "general": {"display_name": "Beta"}},
            }
        },
        entry_id="entry-garden",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _FakeDeviceRegistry()
    snapshot = {
        "plant_id": "garden",
        "plant_name": "Garden",
        "primary_profile_id": "alpha",
        "primary_profile_name": "Alpha",
        "profiles": {
            "alpha": {"name": "Alpha", "general": {"display_name": "Alpha"}},
            "beta": {"name": "Beta", "general": {"display_name": "Beta"}},
        },
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_all_profile_devices_registered(
            hass,
            entry,
            snapshot=snapshot,
        )

    for profile_id, name in ("alpha", "Alpha"), ("beta", "Beta"):
        identifier = profile_device_identifier(entry.entry_id, profile_id)
        device = fake_registry.async_get_device({identifier})
        assert device is not None
        assert device.name == name

    stored = get_entry_data(hass, entry)
    assert stored is not None
    assert set(stored["profiles"].keys()) == {"alpha", "beta"}
    assert stored["profile_devices"]["beta"]["name"] == "Beta"


@pytest.mark.asyncio
async def test_async_sync_entry_devices_adds_canonical_identifiers(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {"mint": {"name": "Mint"}}},
        entry_id="entry-sync",
    )
    entry.add_to_hass(hass)

    fake_registry = _FakeDeviceRegistry()
    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {"mint": {"name": "Mint"}},
    }

    with (
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
            return_value=fake_registry,
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.build_entry_device_info",
            return_value={"identifiers": {("other", "entry")}, "name": "Mint"},
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.build_profile_device_info",
            return_value={"identifiers": {("other", "profile")}, "name": "Mint"},
        ),
    ):
        await async_sync_entry_devices(hass, entry, snapshot=snapshot)

    entry_identifier = entry_device_identifier(entry.entry_id)
    profile_identifier = profile_device_identifier(entry.entry_id, "mint")

    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_identifier in entry_device.identifiers
    assert ("other", "entry") in entry_device.identifiers

    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_identifier in profile_device.identifiers
    assert ("other", "profile") in profile_device.identifiers


@pytest.mark.asyncio
async def test_async_sync_entry_devices_unwraps_mapping_entry_response(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {"mint": {"name": "Mint"}}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _MappingReturningDeviceRegistry(
        entry_device_id="entry-device",
        reject=("via_device",),
        required_profile_args=("via_device_id",),
    )

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await async_sync_entry_devices(
            hass,
            entry,
            snapshot={
                "plant_id": "mint",
                "plant_name": "Mint",
                "profiles": {"mint": {"name": "Mint"}},
            },
        )

    entry_identifier = entry_device_identifier(entry.entry_id)
    entry_device = fake_registry.async_get_device({entry_identifier})
    assert entry_device is not None
    assert entry_device.id == "entry-device"

    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    profile_device = fake_registry.async_get_device({profile_identifier})
    assert profile_device is not None
    assert profile_device.via_device_id == entry_device.id
    assert profile_device.name == "Mint"


@pytest.mark.asyncio
async def test_ensure_all_profile_devices_registered_merges_extra_profiles(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    fake_registry = _FakeDeviceRegistry()
    snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }
    profile_payload = {
        "name": "Mint",
        "general": {"display_name": "Mint", "plant_type": "herb"},
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await ensure_all_profile_devices_registered(
            hass,
            entry,
            snapshot=snapshot,
            extra_profiles={"mint": profile_payload},
        )

    identifier = profile_device_identifier(entry.entry_id, "mint")
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    assert device.name == "Mint"

    stored = get_entry_data(hass, entry)
    assert stored is not None
    assert stored["profiles"]["mint"]["name"] == "Mint"
    assert stored["profile_devices"]["mint"]["name"] == "Mint"


@pytest.mark.asyncio
async def test_async_sync_entry_devices_normalises_profile_ids(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)

    snapshot = {
        "plant_id": "  mint  ",
        "plant_name": "Mint",
        "primary_profile_id": "  mint  ",
        "profiles": {
            "  mint  ": {
                "name": "Mint",
                "general": {"display_name": "Mint"},
            }
        },
    }

    fake_registry = _FakeDeviceRegistry()

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
        return_value=fake_registry,
    ):
        await async_sync_entry_devices(hass, entry, snapshot=snapshot)

    canonical_identifier = profile_device_identifier(entry.entry_id, "mint")
    canonical_device = fake_registry.async_get_device({canonical_identifier})
    assert canonical_device is not None
    assert canonical_device.name == "Mint"

    whitespace_identifier = profile_device_identifier(entry.entry_id, "  mint  ")
    assert fake_registry.async_get_device({whitespace_identifier}) is None


@pytest.mark.asyncio
async def test_backfill_profile_devices_from_options_no_missing_devices(hass):
    entry = _make_entry(
        options={CONF_PROFILES: {"mint": {"name": "Mint", "general": {"display_name": "Mint"}}}},
    )
    entry_data = {
        "profile_devices": {"mint": {"name": "Mint"}},
        "snapshot": {"profiles": {"mint": {"name": "Mint"}}},
    }

    assert await backfill_profile_devices_from_options(hass, entry, entry_data) is False


@pytest.mark.asyncio
async def test_backfill_profile_devices_from_options_registers_missing(hass):
    entry = _make_entry(
        options={CONF_PROFILES: {"mint": {"name": "Mint", "general": {"display_name": "Mint"}}}},
    )
    entry.entry_id = "entry-mint"
    entry_data = {
        "profile_devices": {},
        "snapshot": {"profiles": {}},
    }

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.ensure_all_profile_devices_registered",
    ) as ensure_mock:
        ensure_mock.return_value = asyncio.Future()
        ensure_mock.return_value.set_result(None)
        result = await backfill_profile_devices_from_options(hass, entry, entry_data)

    assert result is True
    ensure_mock.assert_called_once()
    kwargs = ensure_mock.call_args.kwargs
    assert kwargs["extra_profiles"] == {"mint": {"name": "Mint", "general": {"display_name": "Mint"}}}
    assert kwargs["snapshot"] is entry_data["snapshot"]


@pytest.mark.asyncio
async def test_backfill_profile_devices_from_options_uses_cached_entry_data(hass):
    entry = _make_entry(
        options={CONF_PROFILES: {"mint": {"name": "Mint"}}},
    )
    entry.entry_id = "entry-cache"
    domain_data = hass.data.setdefault(DOMAIN, {})
    stored = {
        "config_entry": entry,
        "profile_devices": {},
        "snapshot": {"profiles": {}},
    }
    domain_data[entry.entry_id] = stored

    with patch(
        "custom_components.horticulture_assistant.utils.entry_helpers.ensure_all_profile_devices_registered",
    ) as ensure_mock:
        ensure_mock.return_value = asyncio.Future()
        ensure_mock.return_value.set_result(None)
        result = await backfill_profile_devices_from_options(hass, entry)

    assert result is True
    ensure_mock.assert_called_once()


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

    await store_entry_data(hass, entry)

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
    assert context.has_all_sensors("temperature", "humidity") is True
    assert context.has_sensors("light") is False
    assert context.has_sensors() is True
    assert context.get_threshold("temperature_min") == 12
    info = context.as_device_info()
    assert info["name"] == "Plant"
    assert (DOMAIN, "profile:plant") in info["identifiers"]


def test_profile_context_strips_sensor_whitespace():
    context = ProfileContext(
        id="plant",
        name="Plant",
        sensors={
            "temperature": ["  sensor.temp  ", "sensor.backup  "],
            "humidity": "  sensor.hum  ",
        },
    )

    assert context.sensor_ids_for_roles("temperature") == ("sensor.temp", "sensor.backup")
    assert context.first_sensor("humidity") == "sensor.hum"
    # ``sensor_ids_for_roles`` without args should flatten all roles
    assert context.sensor_ids_for_roles() == ("sensor.temp", "sensor.backup", "sensor.hum")


def test_profile_context_accepts_set_sensor_sequences():
    context = ProfileContext(
        id="plant",
        name="Plant",
        sensors={"light": {" sensor.main ", "sensor.backup"}},
    )

    assert context.sensor_ids_for_roles("light") == ("sensor.backup", "sensor.main")
    assert context.has_all_sensors("light") is True


def test_profile_context_has_sensors_matches_any_role():
    context = ProfileContext(
        id="plant",
        name="Plant",
        sensors={"temperature": ["sensor.temp"]},
    )

    assert context.has_sensors("temperature", "humidity") is True
    assert context.has_all_sensors("temperature", "humidity") is False


@pytest.mark.asyncio
async def test_resolve_profile_image_url_reads_general_section(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "primary", "plant_name": "Primary"},
        options={
            "image_url": "  https://example.com/entry.png  ",
            CONF_PROFILES: {
                "primary": {
                    "name": "Primary",
                    "general": {"image": " https://example.com/general.png "},
                },
            },
        },
    )

    await store_entry_data(hass, entry)

    image = resolve_profile_image_url(hass, entry.entry_id, "primary")
    assert image == "https://example.com/general.png"

    fallback = resolve_profile_image_url(hass, entry.entry_id, "missing")
    assert fallback == "https://example.com/entry.png"


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
    await store_entry_data(hass, entry)

    collection = resolve_profile_context_collection(hass, entry)
    assert isinstance(collection, ProfileContextCollection)
    assert collection.primary_id == "alpha"
    assert {pid for pid, _ in collection.items()} == {"alpha", "beta"}

    primary = collection.primary
    assert primary.name == "Alpha"
    assert primary.sensor_ids_for_roles("temperature")[0] == "sensor.temp"
    assert primary.get_threshold("temperature_min") == 10
    assert primary.has_all_sensors("temperature", "humidity") is True

    secondary = collection.get("beta")
    assert secondary is not None
    assert secondary.name == "Beta"


@pytest.mark.asyncio
async def test_profile_context_preserves_multiple_sensor_links(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = _make_entry(
        data={CONF_PLANT_ID: "delta", CONF_PLANT_NAME: "Delta"},
        options={
            CONF_PROFILES: {
                "delta": {
                    "name": "Delta",
                    "sensors": {
                        "temperature": ["sensor.primary", "sensor.backup"],
                        "humidity": ["sensor.hum"],
                    },
                }
            }
        },
    )

    await store_entry_data(hass, entry)
    collection = resolve_profile_context_collection(hass, entry)
    primary = collection.primary

    assert primary.sensor_ids_for_roles("temperature") == (
        "sensor.primary",
        "sensor.backup",
    )
    assert primary.sensor_ids_for_roles("humidity") == ("sensor.hum",)
    assert primary.has_sensors("temperature", "humidity") is True
    assert primary.has_all_sensors("temperature", "humidity") is True


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


def test_serialise_device_info_accepts_sequence_identifiers():
    info = {
        "identifiers": [[DOMAIN, "profile:beta"], (DOMAIN, "profile:beta")],
        "connections": [["mac", "AA:BB:CC:DD:EE:FF"]],
    }

    serialised = serialise_device_info(info)

    assert serialised["identifiers"] == [[DOMAIN, "profile:beta"]]
    assert serialised["connections"] == [["mac", "AA:BB:CC:DD:EE:FF"]]


def test_serialise_device_info_accepts_frozensets():
    info = {
        "identifiers": frozenset({(DOMAIN, "profile:frozen")}),
        "connections": frozenset({("mac", "11:22:33:44:55:66")}),
    }

    serialised = serialise_device_info(info)

    assert serialised["identifiers"] == [[DOMAIN, "profile:frozen"]]
    assert serialised["connections"] == [["mac", "11:22:33:44:55:66"]]


def test_serialise_device_info_injects_fallback_identifier():
    info = {"name": "Fallback"}

    identifier = (DOMAIN, "profile:identifier")
    serialised = serialise_device_info(info, fallback_identifier=identifier)

    assert serialised["identifiers"] == [[DOMAIN, "profile:identifier"]]
    assert serialised["name"] == "Fallback"


def test_serialise_device_info_uses_via_device_fallback():
    info = {"identifiers": {(DOMAIN, "profile:via")}}

    via_device = (DOMAIN, "entry:device")
    serialised = serialise_device_info(info, fallback_via_device=via_device)

    assert serialised["via_device"] == {"domain": DOMAIN, "id": "entry:device"}


def test_serialise_device_info_preserves_mapping_via_device():
    info = {
        "identifiers": {(DOMAIN, "profile:mapped")},
        "via_device": {"domain": "zha", "id": "0x1234"},
    }

    serialised = serialise_device_info(info)

    assert serialised["via_device"] == {"domain": "zha", "id": "0x1234"}


def test_serialise_device_info_accepts_mapping_identifiers():
    info = {
        "identifiers": {"domain": DOMAIN, "id": "profile:mapped"},
    }

    serialised = serialise_device_info(info)

    assert serialised["identifiers"] == [[DOMAIN, "profile:mapped"]]


def test_serialise_device_info_skips_blank_mapping_identifiers():
    info = {
        "identifiers": {
            "mac": "  AA:BB:CC  ",
            "zigbee": "   ",
            "null": None,
        }
    }

    serialised = serialise_device_info(info)

    assert serialised["identifiers"] == [["mac", "AA:BB:CC"]]


def test_serialise_device_info_supports_nested_mapping_identifiers():
    info = {
        "identifiers": {
            "mac": {"value": "DD:EE"},
            "serial": {"id": "SN-123"},
        }
    }

    serialised = serialise_device_info(info)

    assert serialised["identifiers"] == [["mac", "DD:EE"], ["serial", "SN-123"]]


def test_serialise_device_info_handles_none():
    assert serialise_device_info(None) == {}


def test_serialise_device_info_handles_none_with_fallbacks():
    identifier = (DOMAIN, "profile:none")
    via_device = (DOMAIN, "entry:none")

    serialised = serialise_device_info(
        None,
        fallback_identifier=identifier,
        fallback_via_device=via_device,
    )

    assert serialised["identifiers"] == [[DOMAIN, "profile:none"]]
    assert serialised["via_device"] == {"domain": DOMAIN, "id": "entry:none"}
