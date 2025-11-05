import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.horticulture_assistant.cloudsync.edge_store import EdgeSyncStore
from custom_components.horticulture_assistant.cloudsync.manager import CloudSyncConfig
from custom_components.horticulture_assistant.cloudsync.publisher import CloudSyncPublisher
from custom_components.horticulture_assistant.const import (
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    DOMAIN,
    ISSUE_PROFILE_SENSOR_PREFIX,
    NOTIFICATION_PROFILE_LINEAGE,
    NOTIFICATION_PROFILE_SENSORS,
    NOTIFICATION_PROFILE_VALIDATION,
    PROFILE_SCOPE_DEFAULT,
)
from custom_components.horticulture_assistant.profile import store as profile_store
from custom_components.horticulture_assistant.profile.compat import sync_thresholds
from custom_components.horticulture_assistant.profile.schema import (
    BioProfile,
    FieldAnnotation,
    ResolvedTarget,
    SpeciesProfile,
)
from custom_components.horticulture_assistant.profile.statistics import (
    EVENT_STATS_VERSION,
    NUTRIENT_STATS_VERSION,
)
from custom_components.horticulture_assistant.profile.utils import LineageLinkReport
from custom_components.horticulture_assistant.profile_registry import (
    ProfileRegistry,
    _normalise_sensor_value,
)
from custom_components.horticulture_assistant.utils import entry_helpers as helpers
from custom_components.horticulture_assistant.utils.entry_helpers import (
    entry_device_identifier,
    profile_device_identifier,
    store_entry_data,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytestmark = pytest.mark.asyncio

UTC = getattr(datetime, "UTC", timezone.utc)  # noqa: UP017


async def _make_entry(hass, options=None):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options or {})
    entry.add_to_hass(hass)
    return entry


class FakeDeviceRegistry:
    def __init__(self) -> None:
        self.devices: dict[str, SimpleNamespace] = {}

    @staticmethod
    def _coerce_identifiers(identifiers) -> set[tuple[str, str]]:
        if identifiers is None:
            return set()
        items = identifiers if isinstance(identifiers, list | tuple | set) else [identifiers]
        pairs: set[tuple[str, str]] = set()
        for item in items:
            if isinstance(item, list | tuple) and len(item) == 2:
                pairs.add((str(item[0]), str(item[1])))
            elif isinstance(item, dict):
                domain = item.get("domain")
                ident = item.get("id")
                if domain is not None and ident is not None:
                    pairs.add((str(domain), str(ident)))
        return pairs

    def async_get_device(self, identifiers):
        pairs = self._coerce_identifiers(identifiers)
        for device in self.devices.values():
            if device.identifiers & pairs:
                return device
        return None

    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        pairs = self._coerce_identifiers(identifiers)
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
        device = SimpleNamespace(
            id=device_id,
            identifiers=pairs,
            config_entries={config_entry_id} if config_entry_id else set(),
            name=kwargs.get("name"),
        )
        for field in ("via_device", "via_device_id"):
            setattr(device, field, kwargs.get(field))
        self.devices[device_id] = device
        return device

    def async_remove_device(self, device_id):  # pragma: no cover - helper parity
        self.devices.pop(device_id, None)


class StrictDeviceRegistry(FakeDeviceRegistry):
    """Device registry that requires via_device_id for profile devices."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        pairs = self._coerce_identifiers(identifiers)
        is_profile = any(":profile:" in ident for _, ident in pairs)
        if is_profile and "via_device_id" not in kwargs:
            raise TypeError("via_device_id required for profile devices")
        self.calls.append(
            (
                "profile" if is_profile else "entry",
                {"identifiers": pairs, **kwargs},
            )
        )
        return super().async_get_or_create(
            identifiers=identifiers,
            config_entry_id=config_entry_id,
            **kwargs,
        )

async def test_normalise_sensor_value_sequence_deduplicates():
    """Sequence inputs should be stripped and deduplicated preserving order."""

    result = _normalise_sensor_value(
        [
            " sensor.one  ",
            "sensor.two",
            "sensor.one",
            None,
            "",
            "sensor.two",
        ]
    )

    assert result == ["sensor.one", "sensor.two"]


async def test_missing_species_warning_logged(hass, caplog):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.unknown"}}},
    )
    reg = ProfileRegistry(hass, entry)

    with caplog.at_level(logging.WARNING):
        await reg.async_load()

    assert any("species.unknown" in record.message for record in caplog.records)


async def test_async_add_profile_handles_none_option_profiles(hass):
    """Profiles options set to ``None`` should be treated as empty mapping."""

    entry = await _make_entry(hass, {CONF_PROFILES: None})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Seedling")

    assert pid in entry.options[CONF_PROFILES]


async def test_async_add_profile_registers_device(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    fake_registry = FakeDeviceRegistry()
    update_called = {"flag": False}

    original_update_entry_data = helpers.update_entry_data

    async def _wrapped_update_entry_data(hass_arg, entry_arg):
        update_called["flag"] = True
        return await original_update_entry_data(hass_arg, entry_arg)

    def _update_entry(updated_entry, *, options=None, data=None):
        if options is not None:
            updated_entry.options = options
        if data is not None:
            updated_entry.data = data

    with (
        patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry),
        patch.object(helpers.dr, "async_get", return_value=fake_registry),
        patch(
            "custom_components.horticulture_assistant.profile_registry.update_entry_data",
            side_effect=_wrapped_update_entry_data,
        ),
    ):
        pid = await reg.async_add_profile("Mint")

    assert update_called["flag"] is True
    assert pid in entry.options[CONF_PROFILES]

    identifier = profile_device_identifier(entry.entry_id, pid)
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    assert device.name == "Mint"
    parent_identifier = entry_device_identifier(entry.entry_id)
    parent_device = fake_registry.async_get_device({parent_identifier})
    assert parent_device is not None
    assert getattr(device, "via_device_id", None) == parent_device.id


async def test_async_add_profile_registers_device_real_registry(hass, tmp_path):
    """Adding a profile should register a device using the actual registry."""

    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    registry = ProfileRegistry(hass, entry)
    await registry.async_load()

    pid = await registry.async_add_profile("Mint")

    identifier = profile_device_identifier(entry.entry_id, pid)
    device_registry_module = pytest.importorskip(
        "homeassistant.helpers.device_registry", reason="homeassistant not installed"
    )
    device_registry = device_registry_module.async_get(hass)
    device = device_registry.async_get_device(identifiers={identifier})

    assert device is not None
    assert device.name == "Mint"
    parent = device_registry.async_get_device(
        identifiers={entry_device_identifier(entry.entry_id)}
    )
    assert parent is not None
    assert device.via_device_id == parent.id


async def test_async_add_profile_requires_via_device_id(hass, tmp_path):
    """Profile registration should send via_device_id when registry requires it."""

    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    strict_registry = StrictDeviceRegistry()

    with patch.object(helpers.dr, "async_get", return_value=strict_registry):
        pid = await reg.async_add_profile("Mint")

    identifier = profile_device_identifier(entry.entry_id, pid)
    profile_device = strict_registry.async_get_device({identifier})
    assert profile_device is not None

    parent_identifier = entry_device_identifier(entry.entry_id)
    parent_device = strict_registry.async_get_device({parent_identifier})
    assert parent_device is not None
    assert profile_device.via_device_id == parent_device.id

    profile_calls = [call for call in strict_registry.calls if call[0] == "profile"]
    assert profile_calls
    assert all("via_device_id" in call[1] for call in profile_calls)


async def test_async_load_registers_devices_for_existing_profiles(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "garden", CONF_PLANT_NAME: "Kitchen Garden"},
        options={
            CONF_PROFILES: {
                "p1": {
                    "name": "Herb Bed",
                    "display_name": "Herb Bed",
                    "profile_id": "p1",
                    "plant_id": "p1",
                    "general": {"display_name": "Herb Bed"},
                }
            }
        },
        entry_id="entry-garden",
    )
    entry.add_to_hass(hass)

    registry = ProfileRegistry(hass, entry)
    fake_registry = FakeDeviceRegistry()

    with patch.object(helpers.dr, "async_get", return_value=fake_registry):
        await registry.async_load()

    identifier = profile_device_identifier(entry.entry_id, "p1")
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    assert device.name == "Herb Bed"


async def test_async_add_profile_device_fallback_on_update_failure(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    fake_registry = FakeDeviceRegistry()
    fallback_state = {"called": False}

    original_sync = helpers.async_sync_entry_devices

    async def _wrapped_sync(hass_arg, entry_arg, *, snapshot=None):
        fallback_state["called"] = True
        return await original_sync(hass_arg, entry_arg, snapshot=snapshot)

    def _update_entry(updated_entry, *, options=None, data=None):
        if options is not None:
            updated_entry.options = options
        if data is not None:
            updated_entry.data = data

    with (
        patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry),
        patch.object(helpers.dr, "async_get", return_value=fake_registry),
        patch(
            "custom_components.horticulture_assistant.profile_registry.update_entry_data",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "custom_components.horticulture_assistant.profile_registry.async_sync_entry_devices",
            side_effect=_wrapped_sync,
        ),
    ):
        pid = await reg.async_add_profile("Mint")

    assert fallback_state["called"] is True
    assert pid in entry.options[CONF_PROFILES]

    identifier = profile_device_identifier(entry.entry_id, pid)
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    assert device.name == "Mint"


async def test_async_add_profile_registers_device_when_snapshot_missing(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    fake_registry = FakeDeviceRegistry()

    def _update_entry(updated_entry, *, options=None, data=None):
        if options is not None:
            updated_entry.options = options
        if data is not None:
            updated_entry.data = data

    stub_entry_data = {
        "profile_devices": {},
        "snapshot": {
            "plant_id": "mint",
            "plant_name": "Mint",
            "primary_profile_id": "mint",
            "primary_profile_name": "Mint",
            "profiles": {},
        },
    }

    with (
        patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry),
        patch(
            "custom_components.horticulture_assistant.profile_registry.update_entry_data",
            new=AsyncMock(return_value=stub_entry_data),
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
            return_value=fake_registry,
        ),
    ):
        pid = await reg.async_add_profile("Mint")

    identifier = profile_device_identifier(entry.entry_id, pid)
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    assert device.name == "Mint"


async def test_async_add_profile_registers_device_when_bulk_sync_fails(hass, tmp_path):
    """Profiles should still register devices if bulk sync raises."""

    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint", CONF_PLANT_NAME: "Mint"},
        options={CONF_PROFILES: {}},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)
    await store_entry_data(hass, entry)

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    fake_registry = StrictDeviceRegistry()

    def _update_entry(updated_entry, *, options=None, data=None):
        if options is not None:
            updated_entry.options = options
        if data is not None:
            updated_entry.data = data

    with (
        patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry),
        patch.object(helpers.dr, "async_get", return_value=fake_registry),
        patch(
            "custom_components.horticulture_assistant.profile_registry.ensure_all_profile_devices_registered",
            side_effect=RuntimeError("boom"),
        ),
    ):
        pid = await reg.async_add_profile("Mint")

    identifier = profile_device_identifier(entry.entry_id, pid)
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    parent_identifier = entry_device_identifier(entry.entry_id)
    parent_device = fake_registry.async_get_device({parent_identifier})
    assert parent_device is not None
    assert getattr(device, "via_device_id", None) == parent_device.id


async def test_async_add_profile_sets_species_metadata(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile(
        "Template",
        species_id="global_basil",
        species_display="Global Basil",
    )

    stored = entry.options[CONF_PROFILES][pid]
    assert stored.get("species_display") == "Global Basil"
    local_meta = stored.get("local", {}).get("metadata", {})
    assert local_meta.get("requested_species_id") == "global_basil"


async def test_async_add_profile_sets_cultivar_metadata(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile(
        "Genovese",
        cultivar_id="basil_genovese",
        cultivar_display="Genovese Basil",
    )

    stored = entry.options[CONF_PROFILES][pid]
    assert stored.get("cultivar_display") == "Genovese Basil"
    general = stored.get("general", {})
    assert general.get("cultivar") == "Genovese Basil"
    local_meta = stored.get("local", {}).get("metadata", {})
    assert local_meta.get("requested_cultivar_id") == "basil_genovese"


async def test_async_add_profile_rolls_back_on_save_error(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    with patch.object(reg, "async_save", AsyncMock(side_effect=OSError("disk full"))), pytest.raises(ValueError) as err:
        await reg.async_add_profile("Basil")

    assert "disk full" in str(err.value)
    assert entry.options[CONF_PROFILES] == {}
    assert "basil" not in reg._profiles


async def test_async_add_profile_deduplicates_sequence_sensors(hass):
    """Sensor lists cloned from existing profiles should remove duplicates."""

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "base": {
                    "name": "Base",
                    "sensors": {
                        "moisture": [
                            "sensor.one",
                            "sensor.one",
                            "sensor.two",
                            "sensor.two",
                        ]
                    },
                }
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    clone_id = await reg.async_add_profile("Clone", base_id="base")

    payload = entry.options[CONF_PROFILES][clone_id]
    assert payload["sensors"]["moisture"] == ["sensor.one", "sensor.two"]

    general = payload.get("general") or {}
    sensors = general.get("sensors") or {}
    assert sensors["moisture"] == ["sensor.one", "sensor.two"]

    profile = reg._profiles[clone_id]
    assert profile.general["sensors"]["moisture"] == ["sensor.one", "sensor.two"]


async def test_async_load_skips_invalid_stored_profile(hass, monkeypatch, caplog):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"valid": {"name": "Valid"}}},
    )
    reg = ProfileRegistry(hass, entry)

    async def _fake_load(_self):
        return {"profiles": {"broken": "not-a-mapping"}}

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.Store.async_load",
        _fake_load,
    )

    with caplog.at_level(logging.WARNING):
        await reg.async_load()

    assert any("broken" in record.message for record in caplog.records)
    assert [profile.profile_id for profile in reg.list_profiles()] == ["valid"]


async def test_async_load_ignores_non_mapping_options_profiles(hass, caplog):
    entry = await _make_entry(hass, {CONF_PROFILES: ["not", "a", "mapping"]})
    reg = ProfileRegistry(hass, entry)

    with caplog.at_level(logging.WARNING):
        await reg.async_load()

    assert any("invalid config entry profiles payload" in record.message for record in caplog.records)
    assert reg.list_profiles() == []


async def test_missing_parent_warning_logged(hass, caplog):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "parents": ["cultivar.missing"]}}},
    )
    reg = ProfileRegistry(hass, entry)

    with caplog.at_level(logging.WARNING):
        await reg.async_load()

    assert any("cultivar.missing" in record.message for record in caplog.records)


async def test_profile_device_metadata_populates_defaults_for_blank_fields(hass, monkeypatch):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)

    def _device_info(_hass, _entry_id, _profile_id):
        return {
            "identifiers": {("horticulture_assistant", "custom")},
            "name": "  ",
            "manufacturer": "",
            "model": " ",
        }

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.resolve_profile_device_info",
        _device_info,
    )

    await reg.async_load()
    summaries = reg.summaries()
    assert summaries, "Expected at least one profile summary"

    device_info = summaries[0]["device_info"]
    assert device_info["name"] == "Plant"
    assert device_info["manufacturer"] == "Horticulture Assistant"
    assert device_info["model"] == "Plant Profile"


async def test_profile_device_metadata_injects_missing_identifier(hass, monkeypatch):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)

    def _device_info(_hass, _entry_id, _profile_id):
        return {"identifiers": {("other", "device")}}

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.resolve_profile_device_info",
        _device_info,
    )

    await reg.async_load()
    summaries = reg.summaries()
    assert summaries, "Expected at least one profile summary"

    identifiers = summaries[0]["device_info"].get("identifiers")
    expected = [DOMAIN, f"{entry.entry_id}:profile:p1"]
    assert expected in identifiers


async def test_merge_profile_data_preserves_general_metadata():
    """Stored general metadata should survive profile merges."""

    stored = BioProfile(
        profile_id="p1",
        display_name="Stored",
        general={"template": "veg", CONF_PROFILE_SCOPE: "entry", "sensors": {"temp": "sensor.temp"}},
    )

    overlay = BioProfile(
        profile_id="p1",
        display_name="Overlay",
        general={"sensors": {"humidity": "sensor.hum"}},
    )

    merged = ProfileRegistry._merge_profile_data(stored, overlay)

    assert merged.general.get("template") == "veg"
    assert merged.general.get(CONF_PROFILE_SCOPE) == "entry"
    assert merged.general.get("sensors") == {"temp": "sensor.temp", "humidity": "sensor.hum"}


async def test_lineage_notification_created_and_clears(hass):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.unknown"}}},
    )

    notifications: list[dict] = []
    dismissals: list[dict] = []

    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )
    hass.services.async_register(
        "persistent_notification",
        "dismiss",
        lambda call: dismissals.append(call.data),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await hass.async_block_till_done()

    assert notifications
    latest = notifications[-1]
    assert latest["notification_id"] == NOTIFICATION_PROFILE_LINEAGE
    assert "species.unknown" in latest["message"]

    reg._log_lineage_warnings(LineageLinkReport())
    await hass.async_block_till_done()

    assert any(item.get("notification_id") == NOTIFICATION_PROFILE_LINEAGE for item in dismissals)


async def test_async_delete_profile_clears_lineage_warnings(hass):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.unknown"}}},
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await hass.async_block_till_done()

    assert ("p1", "species.unknown") in reg._lineage_missing_species
    assert ("p1", "species.unknown") in reg._missing_species_issues

    await reg.async_delete_profile("p1")
    await hass.async_block_till_done()

    assert not reg._lineage_missing_species
    assert not reg._missing_species_issues


async def test_async_import_profiles_returns_count(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = await _make_entry(hass, {CONF_PROFILES: {}})
    registry = ProfileRegistry(hass, entry)

    payload = {
        "plant_id": "p1",
        "display_name": "Plant 1",
        "resolved_targets": {},
    }
    (tmp_path / "profiles.json").write_text(json.dumps({"p1": payload}))

    count = await registry.async_import_profiles("profiles.json")

    assert count == 1
    profile = registry.get("p1")
    assert profile is not None
    assert profile.display_name == "Plant 1"
    options_profiles = registry.entry.options.get(CONF_PROFILES, {})
    assert "p1" in options_profiles
    assert options_profiles["p1"]["display_name"] == "Plant 1"


async def test_async_import_profiles_registers_devices(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "import", CONF_PLANT_NAME: "Import"},
        options={CONF_PROFILES: {}},
        entry_id="entry-import",
    )
    entry.add_to_hass(hass)

    registry = ProfileRegistry(hass, entry)
    payload = {
        "plant_id": "p1",
        "profile_id": "p1",
        "display_name": "Imported Plant",
        "general": {"display_name": "Imported Plant"},
    }
    (tmp_path / "profiles.json").write_text(json.dumps({"p1": payload}))

    fake_registry = FakeDeviceRegistry()

    with patch.object(helpers.dr, "async_get", return_value=fake_registry):
        await registry.async_load()
        count = await registry.async_import_profiles("profiles.json")

    assert count == 1
    identifier = profile_device_identifier(entry.entry_id, "p1")
    device = fake_registry.async_get_device({identifier})
    assert device is not None
    assert device.name == "Imported Plant"


async def test_async_import_profiles_updates_existing_options(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Plant 1",
                    "display_name": "Plant 1",
                    "profile_id": "p1",
                    "plant_id": "p1",
                    "general": {"sensors": {"temperature": "sensor.old"}},
                }
            }
        },
    )
    registry = ProfileRegistry(hass, entry)

    updated = BioProfile(
        profile_id="p1",
        display_name="Imported Plant",
        general={"sensors": {"temperature": "sensor.new"}},
    )
    updated.refresh_sections()
    (tmp_path / "profiles.json").write_text(json.dumps({"p1": updated.to_json()}))

    count = await registry.async_import_profiles("profiles.json")

    assert count == 1
    options_profiles = registry.entry.options.get(CONF_PROFILES, {})
    assert options_profiles["p1"]["display_name"] == "Imported Plant"
    general = options_profiles["p1"].get("general", {})
    assert isinstance(general, dict)
    sensors = general.get("sensors", {})
    assert sensors.get("temperature") == "sensor.new"


async def test_missing_species_creates_issue_and_clears_when_resolved(hass, monkeypatch):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.unknown"}}},
    )
    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    assert any(issue_id.startswith("missing_species_p1_") for issue_id, _ in created)
    created_issue_id = next(issue_id for issue_id, _ in created if issue_id.startswith("missing_species_p1_"))

    reg._log_lineage_warnings(LineageLinkReport())

    assert created_issue_id in deleted


@pytest.mark.asyncio
async def test_missing_species_issue_supports_coroutines(hass, monkeypatch):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.unknown"}}},
    )
    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    async def _create_issue(*args, **kwargs):
        created.append((args[2], kwargs))

    async def _delete_issue(*args, **_kwargs):
        deleted.append(args[2])

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=_create_issue,
            async_delete_issue=_delete_issue,
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await hass.async_block_till_done()

    assert any(issue_id.startswith("missing_species_p1_") for issue_id, _ in created)

    reg._log_lineage_warnings(LineageLinkReport())
    await hass.async_block_till_done()

    assert any(issue_id.startswith("missing_species_p1_") for issue_id in deleted)


async def test_missing_species_issue_updates_when_reference_changes(hass, monkeypatch):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.old"}}},
    )
    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    assert created, "Expected an issue for missing species"
    initial_issue_id = created[-1][0]

    created.clear()

    report = LineageLinkReport()
    report.missing_species["p1"] = "species.new"
    reg._log_lineage_warnings(report)

    assert initial_issue_id in deleted
    assert created, "Expected a replacement issue to be created"
    replacement_issue_id = created[-1][0]
    assert replacement_issue_id.startswith("missing_species_p1_")
    assert replacement_issue_id != initial_issue_id
    assert replacement_issue_id not in deleted


async def test_missing_parent_creates_issue_and_clears_when_resolved(hass, monkeypatch):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "parents": ["cultivar.missing"]}}},
    )
    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    assert any(issue_id.startswith("missing_parent_p1") for issue_id, _ in created)

    reg._log_lineage_warnings(LineageLinkReport())

    assert any(issue_id.startswith("missing_parent_p1") for issue_id in deleted)


async def test_missing_parent_issue_ids_do_not_collide(hass, monkeypatch):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})

    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    created.clear()

    report = LineageLinkReport()
    report.missing_parents["p1"] = {"Parent ID", "parent id"}
    reg._log_lineage_warnings(report)

    issue_ids = {issue_id for issue_id, _meta in created}
    assert len(issue_ids) == 2
    for issue_id in issue_ids:
        assert issue_id.startswith("missing_parent_p1_parent_id_")

    reg._log_lineage_warnings(LineageLinkReport())

    for issue_id in issue_ids:
        assert issue_id in deleted


@pytest.mark.asyncio
async def test_profile_validation_creates_and_clears_notification(hass, monkeypatch):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    notifications: list[dict] = []
    dismissals: list[dict] = []

    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )
    hass.services.async_register(
        "persistent_notification",
        "dismiss",
        lambda call: dismissals.append(call.data),
    )

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: ["general.name: required property missing"],
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    assert notifications
    latest = notifications[-1]
    assert latest["notification_id"] == NOTIFICATION_PROFILE_VALIDATION
    assert "required property" in latest["message"]

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: [],
    )

    await reg.async_load()

    assert any(item["notification_id"] == NOTIFICATION_PROFILE_VALIDATION for item in dismissals)


async def test_missing_sensor_creates_issue_and_notification(hass, monkeypatch):
    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Plant",
                    "general": {"sensors": {"temperature": "sensor.missing"}},
                    "sensors": {"temperature": "sensor.missing"},
                }
            }
        },
    )

    notifications: list[dict] = []
    dismissals: list[dict] = []
    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )
    hass.services.async_register(
        "persistent_notification",
        "dismiss",
        lambda call: dismissals.append(call.data),
    )

    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await hass.async_block_till_done()

    assert any(issue_id.startswith(ISSUE_PROFILE_SENSOR_PREFIX) for issue_id, _ in created)
    sensor_issue_id = next(issue_id for issue_id, _ in created if issue_id.startswith(ISSUE_PROFILE_SENSOR_PREFIX))

    assert notifications
    latest = notifications[-1]
    assert latest["notification_id"] == NOTIFICATION_PROFILE_SENSORS
    assert "sensor.missing" in latest["message"]

    # Restore the sensor entity so the issue is cleared
    hass.states.async_set(
        "sensor.missing",
        21,
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )
    await reg.async_load()
    await hass.async_block_till_done()

    assert sensor_issue_id in deleted
    assert any(item["notification_id"] == NOTIFICATION_PROFILE_SENSORS for item in dismissals)


async def test_profile_registry_sensor_conflicts(hass):
    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "alpha": {
                    "name": "Alpha",
                    "general": {"sensors": {"temperature": "sensor.shared"}},
                    "sensors": {"temperature": "sensor.shared"},
                },
                "beta": {
                    "name": "Beta",
                    "general": {"sensors": {"humidity": "sensor.hum"}},
                    "sensors": {"humidity": "sensor.hum"},
                },
            }
        },
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    conflicts = reg.sensor_conflicts("gamma", {"temperature": "sensor.shared", "humidity": "sensor.hum"})

    assert "sensor.shared" in conflicts
    assert conflicts["sensor.shared"]["alpha"][0] == "Alpha"
    assert conflicts["sensor.shared"]["alpha"][1] == ("temperature",)
    assert conflicts["sensor.hum"]["beta"][1] == ("humidity",)


async def test_profile_registry_sensor_conflicts_with_multi_entity_bindings(hass):
    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "alpha": {
                    "name": "Alpha",
                    "general": {"sensors": {"conductivity": ["sensor.ec1", "sensor.ec2"]}},
                    "sensors": {"conductivity": ["sensor.ec1", "sensor.ec2"]},
                },
                "beta": {
                    "name": "Beta",
                    "general": {"sensors": {"moisture": ["sensor.ec2", "sensor.moist"]}},
                    "sensors": {"moisture": ["sensor.ec2", "sensor.moist"]},
                },
            }
        },
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    conflicts = reg.sensor_conflicts(
        "gamma",
        {
            "conductivity": ["sensor.ec2", "sensor.ec2", "sensor.ec3"],
            "moisture": ["sensor.ec1", "sensor.ec1"],
        },
    )

    assert set(conflicts) == {"sensor.ec1", "sensor.ec2"}
    assert conflicts["sensor.ec2"]["alpha"][1] == ("conductivity",)
    assert conflicts["sensor.ec2"]["beta"][1] == ("moisture",)
    assert conflicts["sensor.ec1"]["alpha"][1] == ("conductivity",)


async def test_sensor_conflict_creates_notification(hass):
    hass.states.async_set("sensor.shared", 22, {"device_class": "temperature", "unit_of_measurement": "°C"})

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "alpha": {
                    "name": "Alpha",
                    "general": {"sensors": {"temperature": "sensor.shared"}},
                    "sensors": {"temperature": "sensor.shared"},
                },
                "beta": {
                    "name": "Beta",
                    "general": {"sensors": {"temperature": "sensor.shared"}},
                    "sensors": {"temperature": "sensor.shared"},
                },
            }
        },
    )

    notifications: list[dict] = []
    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await hass.async_block_till_done()

    assert notifications
    latest = notifications[-1]
    assert latest["notification_id"] == NOTIFICATION_PROFILE_SENSORS
    assert "sensor.shared" in latest["message"]
    assert "Alpha" in latest["message"] and "Beta" in latest["message"]


async def test_sensor_warning_creates_notification(hass, monkeypatch):
    hass.states.async_set(
        "sensor.h1",
        45,
        {"device_class": "humidity", "unit_of_measurement": "kPa"},
    )

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Plant",
                    "general": {"sensors": {"humidity": "sensor.h1"}},
                    "sensors": {"humidity": "sensor.h1"},
                }
            }
        },
    )

    notifications: list[dict] = []
    dismissals: list[dict] = []
    hass.services.async_register(
        "persistent_notification",
        "create",
        lambda call: notifications.append(call.data),
    )
    hass.services.async_register(
        "persistent_notification",
        "dismiss",
        lambda call: dismissals.append(call.data),
    )

    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await hass.async_block_till_done()

    assert not created
    assert notifications
    latest = notifications[-1]
    assert latest["notification_id"] == NOTIFICATION_PROFILE_SENSORS
    assert "sensor.h1" in latest["message"]
    assert "unexpected_unit" in latest["message"]

    hass.states.async_set(
        "sensor.h1",
        45,
        {"device_class": "humidity", "unit_of_measurement": "%"},
    )

    await reg.async_load()
    await hass.async_block_till_done()

    assert any(item["notification_id"] == NOTIFICATION_PROFILE_SENSORS for item in dismissals)


async def test_profile_validation_issues_created_and_cleared(hass, monkeypatch):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: ["general.name: required property missing", "general.stage: required"],
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    assert any(issue_id == "invalid_profile_p1" for issue_id, _ in created)
    issue_payload = next(payload for issue_id, payload in created if issue_id == "invalid_profile_p1")
    assert issue_payload["translation_placeholders"]["issue_summary"].startswith("general.name")
    assert "(+1 more)" in issue_payload["translation_placeholders"]["issue_summary"]

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: [],
    )

    await reg.async_load()

    assert "invalid_profile_p1" in deleted


async def test_profile_validation_issue_clears_without_cached_state(hass, monkeypatch):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    created: list[tuple[str, dict]] = []
    deleted: list[str] = []

    class _Severity:
        WARNING = "warning"

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.ir",
        SimpleNamespace(
            IssueSeverity=_Severity,
            async_create_issue=lambda *_args, **kwargs: created.append((_args[2], kwargs)),
            async_delete_issue=lambda *_args: deleted.append(_args[2]),
        ),
    )

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: ["general.name: required property missing"],
    )

    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    assert "invalid_profile_p1" in [issue_id for issue_id, _ in created]

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: [],
    )

    reg_reloaded = ProfileRegistry(hass, entry)
    await reg_reloaded.async_load()

    assert "invalid_profile_p1" in deleted


async def test_update_profile_general_updates_options_and_profile(hass):
    options = {
        CONF_PROFILES: {
            "alpha": {
                "name": "Alpha",
                "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT, "plant_type": "herb"},
            }
        }
    }
    entry = await _make_entry(hass, options)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_update_profile_general(
        "alpha",
        name="Renamed",
        plant_type=None,
        scope="grow_zone",
        species_display="Mentha",
    )

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["name"] == "Renamed"
    assert stored["general"][CONF_PROFILE_SCOPE] == "grow_zone"
    assert "plant_type" not in stored["general"]
    assert stored["species_display"] == "Mentha"

    prof = reg.get("alpha")
    assert prof is not None
    assert prof.display_name == "Renamed"
    assert prof.general.get(CONF_PROFILE_SCOPE) == "grow_zone"
    assert "plant_type" not in prof.general


async def test_update_profile_general_normalises_scope_case(hass):
    options = {CONF_PROFILES: {"alpha": {"name": "Alpha"}}}
    entry = await _make_entry(hass, options)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_update_profile_general("alpha", scope="Crop_Batch")

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["general"][CONF_PROFILE_SCOPE] == "crop_batch"
    profile = reg.get("alpha")
    assert profile is not None
    assert profile.general.get(CONF_PROFILE_SCOPE) == "crop_batch"


async def test_set_profile_sensors_replaces_mapping(hass):
    options = {
        CONF_PROFILES: {
            "alpha": {
                "name": "Alpha",
                "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT, "sensors": {"temperature": "sensor.old"}},
                "sensors": {"temperature": "sensor.old"},
            }
        }
    }
    entry = await _make_entry(hass, options)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    hass.states.async_set("sensor.new_temp", 24, {"device_class": "temperature"})
    await reg.async_set_profile_sensors("alpha", {"temperature": "sensor.new_temp"})

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["general"]["sensors"] == {"temperature": "sensor.new_temp"}
    assert stored["sensors"] == {"temperature": "sensor.new_temp"}


async def test_set_profile_sensors_strips_whitespace(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"plant": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    hass.states.async_set("sensor.temp_sensor", 24, {"device_class": "temperature"})

    await reg.async_set_profile_sensors("plant", {"temperature": " sensor.temp_sensor "})

    stored = entry.options[CONF_PROFILES]["plant"]
    assert stored["general"]["sensors"] == {"temperature": "sensor.temp_sensor"}
    assert stored["sensors"] == {"temperature": "sensor.temp_sensor"}

    prof = reg.get("plant")
    assert prof is not None
    assert prof.general["sensors"] == {"temperature": "sensor.temp_sensor"}


async def test_set_profile_sensors_accepts_sequence_values(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"plant": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    hass.states.async_set("sensor.one", 20, {})
    hass.states.async_set("sensor.two", 19, {})

    await reg.async_set_profile_sensors(
        "plant",
        {
            "environment": [" sensor.one ", "sensor.two", None],
        },
    )

    stored = entry.options[CONF_PROFILES]["plant"]
    assert stored["general"]["sensors"] == {"environment": ["sensor.one", "sensor.two"]}
    assert stored["sensors"] == {"environment": ["sensor.one", "sensor.two"]}

    prof = reg.get("plant")
    assert prof is not None
    assert prof.general["sensors"] == {"environment": ["sensor.one", "sensor.two"]}


async def test_async_link_sensors_strips_whitespace(hass):
    hass.states.async_set(
        "sensor.temp_sensor",
        20,
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )

    entry = await _make_entry(hass, {CONF_PROFILES: {"plant": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_link_sensors("plant", {"temperature": " sensor.temp_sensor "})

    stored = entry.options[CONF_PROFILES]["plant"]
    assert stored["sensors"] == {"temperature": "sensor.temp_sensor"}

    prof = reg._profiles["plant"]
    assert prof.general["sensors"] == {"temperature": "sensor.temp_sensor"}


async def test_update_profile_thresholds_updates_options_and_profile(hass):
    profile_payload = {
        "name": "Alpha",
        "thresholds": {
            "temperature_min": 16.0,
            "temperature_max": 24.0,
            "humidity_min": 35.0,
        },
    }
    sync_thresholds(profile_payload)
    entry = await _make_entry(hass, {CONF_PROFILES: {"alpha": profile_payload}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_update_profile_thresholds(
        "alpha",
        {"temperature_min": 18.5, "temperature_max": 25.5},
        allowed_keys={"temperature_min", "temperature_max"},
    )

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["thresholds"]["temperature_min"] == pytest.approx(18.5)
    assert stored["thresholds"]["temperature_max"] == pytest.approx(25.5)
    resolved = stored["resolved_targets"]
    assert resolved["temperature_min"]["value"] == pytest.approx(18.5)
    assert resolved["temperature_max"]["value"] == pytest.approx(25.5)

    prof = reg.get("alpha")
    assert prof is not None
    assert prof.resolved_targets["temperature_min"].value == pytest.approx(18.5)
    assert prof.resolved_targets["temperature_max"].value == pytest.approx(25.5)

    await reg.async_update_profile_thresholds(
        "alpha",
        {},
        allowed_keys={"humidity_min"},
        removed_keys={"humidity_min"},
    )

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert "humidity_min" not in stored["thresholds"]
    assert "humidity_min" not in stored["resolved_targets"]


async def test_update_profile_thresholds_removes_keys_outside_allowed_set(hass):
    profile_payload = {
        "name": "Alpha",
        "thresholds": {
            "temperature_min": 16.0,
            "temperature_max": 24.0,
            "humidity_min": 35.0,
        },
    }
    sync_thresholds(profile_payload)
    entry = await _make_entry(hass, {CONF_PROFILES: {"alpha": profile_payload}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_update_profile_thresholds(
        "alpha",
        {"temperature_min": 18.0},
        allowed_keys={"temperature_min"},
        removed_keys={"humidity_min"},
    )

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["thresholds"]["temperature_min"] == pytest.approx(18.0)
    assert "humidity_min" not in stored["thresholds"]
    assert "humidity_min" not in stored.get("resolved_targets", {})


async def test_update_profile_thresholds_skips_updates_when_allowed_empty(hass):
    profile_payload = {
        "name": "Alpha",
        "thresholds": {
            "temperature_min": 16.0,
        },
    }
    sync_thresholds(profile_payload)
    entry = await _make_entry(hass, {CONF_PROFILES: {"alpha": profile_payload}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_update_profile_thresholds(
        "alpha",
        {"temperature_min": 18.0},
        allowed_keys=set(),
    )

    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["thresholds"]["temperature_min"] == pytest.approx(16.0)
    resolved = stored["resolved_targets"]["temperature_min"]["value"]
    assert resolved == pytest.approx(16.0)

    prof = reg.get("alpha")
    assert prof is not None
    assert prof.resolved_targets["temperature_min"].value == pytest.approx(16.0)


async def test_update_profile_thresholds_validates_bounds(hass):
    profile_payload = {
        "name": "Alpha",
        "thresholds": {
            "temperature_min": 16.0,
            "temperature_max": 24.0,
        },
    }
    sync_thresholds(profile_payload)
    entry = await _make_entry(hass, {CONF_PROFILES: {"alpha": profile_payload}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    with pytest.raises(ValueError):
        await reg.async_update_profile_thresholds(
            "alpha",
            {"temperature_min": 40.0},
            allowed_keys={"temperature_min"},
        )


async def test_update_profile_thresholds_rejects_non_finite(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"alpha": {"name": "Alpha"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    with pytest.raises(ValueError, match="non-finite threshold value"):
        await reg.async_update_profile_thresholds(
            "alpha",
            {"temperature_max": float("nan")},
        )

    with pytest.raises(ValueError, match="non-finite threshold value"):
        await reg.async_update_profile_thresholds(
            "alpha",
            {"temperature_max": float("inf")},
        )


async def test_update_profile_thresholds_rejects_booleans(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"alpha": {"name": "Alpha"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    with pytest.raises(ValueError, match="invalid threshold temperature_max"):
        await reg.async_update_profile_thresholds(
            "alpha",
            {"temperature_max": True},
        )


async def test_set_profile_sensors_raises_on_invalid_entities(hass):
    options = {
        CONF_PROFILES: {
            "alpha": {
                "name": "Alpha",
                "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
            }
        }
    }
    entry = await _make_entry(hass, options)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    with pytest.raises(ValueError):
        await reg.async_set_profile_sensors("alpha", {"temperature": "sensor.missing"})


async def test_profile_threshold_violations_logged(hass, monkeypatch):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.profile_registry.validate_profile_dict",
        lambda _payload, _schema: [],
    )

    profile = BioProfile(profile_id="p1", display_name="Plant")
    profile.resolved_targets["temperature_min"] = ResolvedTarget(
        value=90.0,
        annotation=FieldAnnotation(source_type="manual", method="manual"),
        citations=[],
    )
    profile.resolved_targets["temperature_max"] = ResolvedTarget(
        value=10.0,
        annotation=FieldAnnotation(source_type="manual", method="manual"),
        citations=[],
    )

    issues = reg._validate_profile(profile)
    assert any("temperature_min" in item for item in issues)
    assert reg._validation_issues["p1"]


async def test_initialize_merges_storage_and_options(hass):
    """Profiles in storage and options are merged."""

    prof = BioProfile(profile_id="p1", display_name="Stored")
    await profile_store.async_save_profile(hass, prof)

    entry = await _make_entry(hass, {CONF_PROFILES: {"p2": {"name": "Opt"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    ids = {p.profile_id for p in reg.list_profiles()}
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


async def test_async_load_merges_option_sensors_overrides_storage(hass):
    """Sensors from config entry options override stored mappings."""

    stored = BioProfile(profile_id="p1", display_name="Stored")
    stored.general["sensors"] = {"temperature": "sensor.old", "moisture": "sensor.m"}
    await profile_store.async_save_profile(hass, stored)

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Stored",
                    "sensors": {"temperature": "sensor.new", "humidity": "sensor.h"},
                }
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    prof = reg.get("p1")
    assert prof is not None
    assert prof.general["sensors"] == {
        "temperature": "sensor.new",
        "moisture": "sensor.m",
        "humidity": "sensor.h",
    }
    assert prof.general["sensors"] is not entry.options[CONF_PROFILES]["p1"]["sensors"]


async def test_replace_sensor_updates_entry_and_registry(hass):
    """Replacing a sensor updates both entry options and registry state."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_replace_sensor("p1", "temperature", "sensor.temp")

    assert entry.options[CONF_PROFILES]["p1"]["sensors"]["temperature"] == "sensor.temp"
    prof = reg.get("p1")
    assert prof.general["sensors"]["temperature"] == "sensor.temp"
    sections = entry.options[CONF_PROFILES]["p1"].get("sections", {})
    assert sections["local"]["general"]["sensors"]["temperature"] == "sensor.temp"
    refreshed_local = prof.refresh_sections().local
    assert refreshed_local.general["sensors"]["temperature"] == "sensor.temp"


async def test_replace_sensor_unknown_profile_raises(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    with pytest.raises(ValueError):
        await reg.async_replace_sensor("missing", "temperature", "sensor.temp")


async def test_replace_sensor_strips_entity_id_whitespace(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_replace_sensor("p1", "temperature", " sensor.temp ")

    assert entry.options[CONF_PROFILES]["p1"]["sensors"]["temperature"] == "sensor.temp"
    prof = reg.get("p1")
    assert prof.general["sensors"]["temperature"] == "sensor.temp"


async def test_replace_sensor_rejects_blank_entity_id(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    with pytest.raises(ValueError):
        await reg.async_replace_sensor("p1", "temperature", "   ")


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


async def test_collect_onboarding_warnings_reports_issues(hass):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Plant", "species": "species.unknown"}}},
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    reg._validation_issue_summaries["p1"] = "sensor validation failed"
    reg._sensor_missing_entities["p1"] = ("sensor.one",)
    reg._sensor_warning_messages["p1"] = ("temperature -> sensor.one: unexpected_unit",)

    warnings = reg.collect_onboarding_warnings()
    assert any("missing species" in warning for warning in warnings)
    assert "sensor validation failed" in warnings
    assert any("missing sensors" in warning for warning in warnings)
    assert any("sensor configuration warnings" in warning for warning in warnings)


async def test_summaries_return_serialisable_data(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    await reg.async_replace_sensor("p1", "humidity", "sensor.h")
    summaries = reg.summaries()
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["plant_id"] == "p1"
    assert summary["name"] == "Plant"
    assert summary["profile_type"] == "line"
    assert summary["sensors"] == {"humidity": "sensor.h"}
    assert summary["targets"] == {}
    assert summary["tags"] == []
    assert summary["device_identifier"] == {
        "domain": DOMAIN,
        "id": f"{entry.entry_id}:profile:p1",
    }
    assert summary["device_info"]["identifiers"] == [
        [DOMAIN, f"{entry.entry_id}:profile:p1"],
    ]
    assert summary["device_info"]["name"] == "Plant"
    # Ensure payload is JSON serialisable
    json.dumps(summary)


async def test_iteration_and_len(hass):
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    assert len(reg) == 1
    assert [p.profile_id for p in reg] == ["p1"]


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


async def test_record_run_event_appends_and_persists(hass):
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    result = await reg.async_record_run_event(
        "cultivar.1",
        {"run_id": "run-1", "started_at": "2024-01-01T00:00:00Z"},
    )

    profile = reg.get("cultivar.1")
    assert profile is not None
    assert len(profile.run_history) == 1
    assert result.profile_id == "cultivar.1"
    assert profile.run_history[0].species_id == "species.1"
    assert profile.updated_at is not None

    stored = await profile_store.async_load_profile(hass, "cultivar.1")
    assert stored is not None and len(stored.run_history) == 1


async def test_record_run_event_rejects_invalid_success_rate(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Run Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_run_event(
            profile_id,
            {
                "run_id": "run-oob",
                "profile_id": profile_id,
                "started_at": "2024-05-01T00:00:00Z",
                "success_rate": 1.5,
            },
        )

    assert "success_rate" in str(excinfo.value)


async def test_record_run_event_rejects_naive_timestamp(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Run Timestamp Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_run_event(
            profile_id,
            {
                "run_id": "run-naive",
                "started_at": "2024-05-01T00:00:00",
            },
        )

    assert "started_at" in str(excinfo.value)


async def test_record_harvest_event_updates_statistics(hass):
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    now = datetime.now(UTC)
    run_started = (now - timedelta(days=10)).isoformat()
    run_finished = (now - timedelta(days=5)).isoformat()
    recent_harvest = (now - timedelta(days=3)).isoformat()

    await reg.async_record_run_event(
        "cultivar.1",
        {
            "run_id": "run-1",
            "started_at": run_started,
            "ended_at": run_finished,
            "environment": {"temperature_c": 23.5, "humidity_percent": 55},
        },
    )
    event = await reg.async_record_harvest_event(
        "cultivar.1",
        {
            "harvest_id": "harvest-1",
            "harvested_at": recent_harvest,
            "yield_grams": 125.5,
            "area_m2": 2.5,
        },
    )

    cultivar_prof = reg.get("cultivar.1")
    assert cultivar_prof is not None
    assert len(cultivar_prof.harvest_history) == 1
    assert event.run_id == "run-1"
    assert cultivar_prof.statistics and cultivar_prof.statistics[0].scope == "cultivar"
    metrics = cultivar_prof.statistics[0].metrics
    assert metrics["total_yield_grams"] == 125.5
    assert metrics["average_yield_density_g_m2"] == round(125.5 / 2.5, 3)
    cultivar_snapshot = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert cultivar_snapshot is not None
    assert cultivar_snapshot.payload["yields"]["total_grams"] == pytest.approx(125.5)
    assert cultivar_snapshot.payload["window_totals"]["7d"]["harvest_count"] == 1.0
    assert cultivar_snapshot.payload["window_totals"]["7d"]["total_yield_grams"] == pytest.approx(125.5)
    assert cultivar_snapshot.payload["days_since_last_harvest"] == pytest.approx(3.0, abs=0.05)
    assert cultivar_snapshot.payload["runs_tracked"] == 1

    species_prof = reg.get("species.1")
    assert species_prof is not None
    species_metrics = species_prof.statistics[0].metrics
    assert species_metrics["total_yield_grams"] == 125.5
    species_snapshot = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert species_snapshot is not None
    contributors = {item["profile_id"]: item for item in species_snapshot.payload["contributors"]}
    assert contributors["cultivar.1"]["total_yield_grams"] == pytest.approx(125.5)
    assert species_snapshot.payload["window_totals"]["7d"]["harvest_count"] == 1.0

    stored_cultivar = await profile_store.async_load_profile(hass, "cultivar.1")
    assert stored_cultivar is not None and len(stored_cultivar.harvest_history) == 1
    stored_snapshot = next(
        (snap for snap in stored_cultivar.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert stored_snapshot is not None

    cultivar_env = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == "environment/v1"),
        None,
    )
    assert cultivar_env is not None
    assert cultivar_env.payload["metrics"]["avg_temperature_c"] == pytest.approx(23.5)
    assert cultivar_env.payload["runs_recorded"] == 1

    species_env = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == "environment/v1"),
        None,
    )
    assert species_env is not None
    assert species_env.payload["runs_recorded"] >= 1


async def test_harvest_window_totals_track_recent_windows(hass):
    species = BioProfile(profile_id="species.window", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.window",
        display_name="Window Cultivar",
        profile_type="cultivar",
        species="species.window",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    now = datetime.now(UTC)
    events = [
        (now - timedelta(days=40), 90.0, 1.5, 30),
        (now - timedelta(days=20), 80.0, 1.2, 20),
        (now - timedelta(days=3), 120.0, 2.5, 40),
    ]

    for idx, (timestamp, yield_grams, area, fruit) in enumerate(events, start=1):
        await reg.async_record_harvest_event(
            "cultivar.window",
            {
                "harvest_id": f"harvest-{idx}",
                "harvested_at": timestamp.isoformat(),
                "yield_grams": yield_grams,
                "area_m2": area,
                "fruit_count": fruit,
            },
        )

    profile = reg.get("cultivar.window")
    assert profile is not None
    snapshot = next(
        (snap for snap in profile.computed_stats if snap.stats_version == "yield/v1"),
        None,
    )
    assert snapshot is not None
    windows = snapshot.payload["window_totals"]
    assert windows["7d"]["harvest_count"] == 1.0
    assert windows["7d"]["total_yield_grams"] == pytest.approx(120.0)
    assert windows["30d"]["harvest_count"] == 2.0
    assert windows["30d"]["total_yield_grams"] == pytest.approx(200.0)
    assert windows["90d"]["harvest_count"] == 3.0
    assert windows["90d"]["fruit_count"] == pytest.approx(90.0)
    metrics = snapshot.payload["metrics"]
    assert metrics["total_fruit_count"] == pytest.approx(90.0)
    assert metrics["days_since_last_harvest"] == pytest.approx(3.0, abs=0.05)


async def test_record_harvest_event_rejects_negative_yield(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Validation Test")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_harvest_event(
            profile_id,
            {
                "harvest_id": "bad",
                "profile_id": profile_id,
                "harvested_at": "2024-07-01T00:00:00Z",
                "yield_grams": -5,
            },
        )

    assert "yield_grams" in str(excinfo.value)


async def test_record_nutrient_event_updates_snapshots(hass):
    species = BioProfile(profile_id="species.1", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.1",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.1",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    event = await reg.async_record_nutrient_event(
        "cultivar.1",
        {
            "event_id": "feed-1",
            "applied_at": "2024-03-01T08:00:00Z",
            "product_id": "fert-001",
            "product_name": "Grow A",
            "solution_volume_liters": 12.5,
            "concentration_ppm": 850,
        },
    )

    cultivar_prof = reg.get("cultivar.1")
    assert cultivar_prof is not None
    assert len(cultivar_prof.nutrient_history) == 1
    assert event.product_name == "Grow A"
    snapshot = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == NUTRIENT_STATS_VERSION),
        None,
    )
    assert snapshot is not None
    metrics = snapshot.payload["metrics"]
    assert metrics["total_events"] == pytest.approx(1.0)
    assert metrics["total_volume_liters"] == pytest.approx(12.5)
    assert snapshot.payload["last_event"]["product_name"] == "Grow A"

    species_prof = reg.get("species.1")
    assert species_prof is not None
    species_snapshot = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == NUTRIENT_STATS_VERSION),
        None,
    )
    assert species_snapshot is not None


async def test_record_nutrient_event_rejects_bad_metadata(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Nutrient Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_nutrient_event(
            profile_id,
            {
                "event_id": "feed-err",
                "applied_at": "2024-03-01T08:00:00Z",
                "metadata": ["invalid"],
            },
        )

    assert "metadata" in str(excinfo.value)


async def test_record_nutrient_event_flags_set_additives(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Nutrient Additives Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_nutrient_event(
            profile_id,
            {
                "event_id": "feed-set",
                "applied_at": "2024-03-01T08:00:00Z",
                "additives": {"calmag", "silica"},
            },
        )

    assert "additives" in str(excinfo.value)


async def test_record_cultivation_event_rejects_non_sequence_tags(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Tag Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_cultivation_event(
            profile_id,
            {
                "event_id": "event-1",
                "occurred_at": "2024-03-01T08:00:00Z",
                "event_type": "inspection",
                "tags": "not-a-list",
            },
        )

    assert "tags" in str(excinfo.value)


async def test_record_nutrient_event_rejects_invalid_ph(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Nutrient Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_nutrient_event(
            profile_id,
            {
                "event_id": "invalid-ph",
                "profile_id": profile_id,
                "applied_at": "2024-08-10T18:04:00Z",
                "ph": 15.2,
            },
        )

    assert "ph" in str(excinfo.value)


async def test_record_cultivation_event_updates_statistics(hass):
    species = BioProfile(profile_id="species.2", display_name="Species", profile_type="species")
    cultivar = BioProfile(
        profile_id="cultivar.2",
        display_name="Cultivar",
        profile_type="cultivar",
        species="species.2",
    )
    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    event = await reg.async_record_cultivation_event(
        "cultivar.2",
        {
            "event_id": "evt-1",
            "occurred_at": "2024-04-01T09:30:00Z",
            "event_type": "pruning",
            "title": "Canopy prune",
            "notes": "Removed lower leaves",
            "metric_value": 3.2,
            "metric_unit": "cm",
        },
    )

    cultivar_prof = reg.get("cultivar.2")
    assert cultivar_prof is not None
    assert len(cultivar_prof.event_history) == 1
    assert event.event_type == "pruning"
    snapshot = next(
        (snap for snap in cultivar_prof.computed_stats if snap.stats_version == EVENT_STATS_VERSION),
        None,
    )
    assert snapshot is not None
    metrics = snapshot.payload["metrics"]
    assert metrics["total_events"] == pytest.approx(1.0)
    assert snapshot.payload["last_event"]["title"] == "Canopy prune"

    species_prof = reg.get("species.2")
    assert species_prof is not None
    species_snapshot = next(
        (snap for snap in species_prof.computed_stats if snap.stats_version == EVENT_STATS_VERSION),
        None,
    )
    assert species_snapshot is not None
    species_metrics = species_snapshot.payload["metrics"]
    assert species_metrics["total_events"] == pytest.approx(1.0)
    contributors = species_snapshot.payload.get("contributors") or []
    assert any(item.get("profile_id") == "cultivar.2" for item in contributors)


async def test_record_cultivation_event_requires_event_type(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    profile_id = await reg.async_add_profile("Cultivation Validation")

    with pytest.raises(ValueError) as excinfo:
        await reg.async_record_cultivation_event(
            profile_id,
            {
                "event_id": "missing-type",
                "profile_id": profile_id,
                "occurred_at": "2024-09-01T12:00:00Z",
                "event_type": "",
            },
        )

    assert "event_type" in str(excinfo.value)


async def test_relink_profiles_populates_species_relationships(hass):
    species = SpeciesProfile(profile_id="species.alpha", display_name="Alpha")
    cultivar = BioProfile(
        profile_id="cultivar.beta",
        display_name="Beta",
        profile_type="cultivar",
    )
    cultivar.parents = ["species.alpha"]

    await profile_store.async_save_profile(hass, species)
    await profile_store.async_save_profile(hass, cultivar)

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    species_prof = reg.get("species.alpha")
    cultivar_prof = reg.get("cultivar.beta")

    assert species_prof is not None
    assert cultivar_prof is not None
    assert cultivar_prof.species_profile_id == "species.alpha"
    assert species_prof.cultivar_ids == ["cultivar.beta"]
    assert cultivar_prof.parents[0] == "species.alpha"
    assert cultivar_prof.lineage and cultivar_prof.lineage[0].profile_id == "cultivar.beta"
    assert any(entry.profile_id == "species.alpha" for entry in cultivar_prof.lineage)
    species_entry = next((entry for entry in cultivar_prof.lineage if entry.profile_id == "species.alpha"), None)
    assert species_entry is not None and species_entry.role in {"species", "parent"}


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


async def test_export_preserves_unicode_characters(hass, tmp_path):
    entry = await _make_entry(
        hass,
        {CONF_PROFILES: {"p1": {"name": "Señor Basil"}}},
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()
    path = tmp_path / "unicode.json"
    await reg.async_export(path)
    text = path.read_text(encoding="utf-8")
    assert "Señor" in text
    payload = json.loads(text)
    assert payload[0]["display_name"] == "Señor Basil"


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
    sections = entry.options[CONF_PROFILES][pid]["sections"]
    assert sections["local"]["general"]["sensors"]["temperature"] == "sensor.t"


async def test_add_profile_copy_preserves_sequence_sensors(hass):
    """Profiles cloned from options retain multi-entity sensor mappings."""

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Plant",
                    "sensors": {
                        "environment": ["sensor.one", " sensor.two "],
                        "temperature": "sensor.temp",
                    },
                    "general": {
                        "sensors": {
                            "environment": ["sensor.one", " sensor.two ", None],
                            "temperature": "sensor.temp",
                        }
                    },
                }
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone Multi", base_id="p1")

    sensors = entry.options[CONF_PROFILES][pid]["sensors"]
    assert sensors["environment"] == ["sensor.one", "sensor.two"]
    assert sensors["temperature"] == "sensor.temp"

    general = entry.options[CONF_PROFILES][pid]["general"]["sensors"]
    assert general["environment"] == ["sensor.one", "sensor.two"]
    assert general["temperature"] == "sensor.temp"

    profile = reg.get(pid)
    assert profile is not None
    assert profile.general["sensors"]["environment"] == ["sensor.one", "sensor.two"]
    assert profile.general["sensors"]["temperature"] == "sensor.temp"


async def test_add_profile_clone_preserves_local_general_overrides(hass):
    """Local-only sensor bindings survive cloning alongside global sensors."""

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Plant",
                    "sensors": {"temperature": " sensor.temp "},
                    "general": {"sensors": {"temperature": "sensor.temp"}},
                    "local": {
                        "general": {
                            "sensors": {
                                "temperature": "sensor.temp",
                                "soil_moisture": " sensor.soil ",
                                "humidity": None,
                            }
                        }
                    },
                }
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone Local Overrides", base_id="p1")

    stored = entry.options[CONF_PROFILES][pid]
    assert stored["sensors"]["temperature"] == "sensor.temp"
    assert stored["general"]["sensors"]["temperature"] == "sensor.temp"

    local_general = stored["local"]["general"]
    assert local_general["sensors"]["temperature"] == "sensor.temp"
    assert local_general["sensors"]["soil_moisture"] == "sensor.soil"
    assert "humidity" not in local_general["sensors"]

    profile = reg.get(pid)
    assert profile is not None
    assert profile.general["sensors"]["temperature"] == "sensor.temp"
    assert profile.local.general["sensors"]["soil_moisture"] == "sensor.soil"


async def test_add_profile_clone_strips_invalid_sensor_values(hass):
    """Cloned profiles should drop whitespace-only or null sensor bindings."""

    entry = await _make_entry(
        hass,
        {
            CONF_PROFILES: {
                "p1": {
                    "name": "Plant",
                    "sensors": {"temperature": "  ", "humidity": None},
                    "general": {
                        "template": "veg",
                        "sensors": {"temperature": "  ", "humidity": None},
                    },
                }
            }
        },
    )
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone Clean", base_id="p1")

    stored = entry.options[CONF_PROFILES][pid]
    assert "sensors" not in stored

    general = stored.get("general", {})
    assert general.get("template") == "veg"
    assert "sensors" not in general or not general["sensors"]

    local_general = stored.get("local", {}).get("general", {})
    assert "sensors" not in local_general or not local_general["sensors"]

    profile = reg.get(pid)
    assert profile is not None
    assert not profile.general.get("sensors")


async def test_add_profile_clone_from_storage_profile(hass):
    """Profiles persisted only in storage can still be used as clone sources."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)

    base_profile = BioProfile(
        profile_id="base",
        display_name="Base",
        resolved_targets={
            "temperature": ResolvedTarget(
                value=21.5,
                annotation=FieldAnnotation(source_type="manual"),
            )
        },
        general={
            "sensors": {"temperature": "sensor.base"},
            CONF_PROFILE_SCOPE: "grow_zone",
        },
    )
    base_profile.refresh_sections()
    stored_payload = base_profile.to_json()

    class DummyStore:
        def __init__(self):
            self.saved = None

        async def async_load(self):
            return {"profiles": {"base": stored_payload}}

        async def async_save(self, data):
            self.saved = data

    reg._store = DummyStore()  # type: ignore[assignment]

    await reg.async_load()

    pid = await reg.async_add_profile("Clone Profile", base_id="base")

    assert pid == "clone_profile"
    clone_options = entry.options[CONF_PROFILES][pid]
    assert clone_options["sensors"]["temperature"] == "sensor.base"
    assert clone_options["general"][CONF_PROFILE_SCOPE] == "grow_zone"
    assert clone_options["general"]["sensors"]["temperature"] == "sensor.base"

    clone_profile = reg.get(pid)
    assert clone_profile is not None
    assert clone_profile.general[CONF_PROFILE_SCOPE] == "grow_zone"
    assert clone_profile.general["sensors"]["temperature"] == "sensor.base"


async def test_add_profile_sets_new_plant_id_in_options(hass):
    """New profiles store their own plant_id in config entry options."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"base": {"name": "Base", "plant_id": "base"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Clone", base_id="base")

    assert pid != "base"
    assert entry.options[CONF_PROFILES][pid]["plant_id"] == pid


async def test_add_profile_sets_plant_id_for_new_entries(hass):
    """Profiles created from scratch include plant_id metadata."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Rosemary")

    assert entry.options[CONF_PROFILES][pid]["plant_id"] == pid
    sections = entry.options[CONF_PROFILES][pid]["sections"]
    assert sections["local"]["general"].get("sensors", {}) == {}
    assert reg.get(pid).refresh_sections().local.general.get("sensors", {}) == {}


async def test_add_profile_generates_sequential_suffixes(hass):
    """New profiles receive sequentially numbered identifiers."""

    entry = await _make_entry(hass, {CONF_PROFILES: {"tomato": {"name": "Tomato"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    first = await reg.async_add_profile("Tomato")
    assert first == "tomato_1"

    entry.options[CONF_PROFILES]["tomato_1"] = {"name": "Tomato #1"}

    second = await reg.async_add_profile("Tomato")
    assert second == "tomato_2"


async def test_add_profile_custom_scope(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("North Bay", scope="grow_zone")

    assert entry.options[CONF_PROFILES][pid][CONF_PROFILE_SCOPE] == "grow_zone"
    prof = reg.get(pid)
    assert prof is not None
    assert prof.general[CONF_PROFILE_SCOPE] == "grow_zone"


async def test_add_profile_normalises_scope_case(hass):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_add_profile("Case Scope", scope="  Grow_Zone  ")

    stored = entry.options[CONF_PROFILES][pid]
    assert stored[CONF_PROFILE_SCOPE] == "grow_zone"
    general = stored.get("general", {})
    assert general.get(CONF_PROFILE_SCOPE) == "grow_zone"
    profile = reg.get(pid)
    assert profile is not None
    assert profile.general.get(CONF_PROFILE_SCOPE) == "grow_zone"


async def test_import_template_creates_profile(hass):
    """Bundled templates can seed new profiles."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_import_template("basil")

    prof = reg.get(pid)
    assert prof and prof.display_name == "Basil"
    assert prof.species == "Ocimum basilicum"


@pytest.mark.asyncio
async def test_import_template_updates_entry_options(hass):
    """Imported templates should immediately populate config entry options."""

    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    pid = await reg.async_import_template("basil")

    stored = entry.options[CONF_PROFILES][pid]
    assert stored["name"] == "Basil"
    assert stored["thresholds"]["min_moisture"] == 30
    assert stored["resolved_targets"]["max_moisture"]["value"] == 60
    assert stored["library"]["identity"]["common_name"] == "Basil"


async def test_cloud_publisher_records_profile_and_events(hass, tmp_path):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    store = EdgeSyncStore(tmp_path / "sync.db")
    config = CloudSyncConfig(
        enabled=True,
        base_url="https://cloud.example",
        tenant_id="tenant-1",
        device_token="device-token",
        organization_id="org-1",
    )
    manager = SimpleNamespace(store=store, config=config, record_offline_enqueue=lambda **_kwargs: None)
    publisher = CloudSyncPublisher(manager, device_id="edge-1")
    reg.attach_cloud_publisher(publisher)

    profile_id = await reg.async_add_profile("Cloud Basil")
    harvest = await reg.async_record_harvest_event(
        profile_id,
        {
            "harvest_id": "harvest-1",
            "profile_id": profile_id,
            "harvested_at": "2025-01-10T00:00:00Z",
            "yield_grams": 120.5,
        },
    )

    events = store.get_outbox_batch(20)
    profile_events = [event for event in events if event.entity_type == "profile" and event.entity_id == profile_id]
    assert profile_events, "profile upsert should be queued"
    assert profile_events[-1].vector.counter == len(profile_events)

    harvest_events = [event for event in events if event.entity_type == "harvest_event"]
    assert any(event.entity_id == harvest.harvest_id for event in harvest_events)

    computed_events = [event for event in events if event.entity_type == "computed" and event.entity_id == profile_id]
    assert computed_events, "computed stats should be enqueued"
    latest = computed_events[-1]
    assert latest.metadata.get("stats_version")
    assert latest.patch and "versions" in latest.patch


async def test_history_exporter_persists_events(hass, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))
    entry = await _make_entry(hass, {CONF_PROFILES: {"p1": {"name": "History Plant"}}})
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    await reg.async_record_harvest_event(
        "p1",
        {
            "harvest_id": "harvest-1",
            "profile_id": "p1",
            "harvested_at": "2025-02-10T00:00:00+00:00",
            "yield_grams": 42.0,
        },
    )

    history_dir = tmp_path / "custom_components" / "horticulture_assistant" / "data" / "local" / "history" / "p1"
    log_path = history_dir / "harvest_events.jsonl"
    assert log_path.is_file()
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["harvest_id"] == "harvest-1"

    index_path = history_dir.parent / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["p1"]["counts"]["harvest"] == 1


async def test_cloud_publisher_defers_until_ready(hass, tmp_path):
    entry = await _make_entry(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_load()

    store = EdgeSyncStore(tmp_path / "sync-disabled.db")
    config = CloudSyncConfig(enabled=False)
    offline_notifications: list[dict[str, Any]] = []
    manager = SimpleNamespace(
        store=store,
        config=config,
        record_offline_enqueue=lambda **kwargs: offline_notifications.append(kwargs),
    )
    publisher = CloudSyncPublisher(manager, device_id="edge-2")
    reg.attach_cloud_publisher(publisher)

    profile_id = await reg.async_add_profile("Offline Seedling")

    queued_events = store.get_outbox_batch(10)
    profile_events = [
        event for event in queued_events if event.entity_type == "profile" and event.entity_id == profile_id
    ]
    assert profile_events, "profile upserts should be queued even when the publisher is offline"
    assert profile_events[-1].metadata.get("queued_offline") is True
    assert offline_notifications and offline_notifications[-1].get("reason") == "not_ready"
    assert reg._cloud_pending_snapshot is True

    manager.config.enabled = True
    manager.config.base_url = "https://cloud.example"
    manager.config.tenant_id = "tenant-2"
    manager.config.device_token = "device-token"
    reg.publish_full_snapshot()

    events = store.get_outbox_batch(10)
    assert any(event.entity_type == "profile" and event.entity_id == profile_id for event in events)
    assert any(
        event.metadata.get("initial_sync")
        for event in events
        if event.entity_type == "profile" and event.entity_id == profile_id
    )
