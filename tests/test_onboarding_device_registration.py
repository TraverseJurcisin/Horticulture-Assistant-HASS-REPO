import sys
import types
from collections.abc import Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

import custom_components.horticulture_assistant as hca_module
from custom_components.horticulture_assistant import async_setup_entry
from custom_components.horticulture_assistant.config_flow import OptionsFlow
from custom_components.horticulture_assistant.const import (
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    DOMAIN,
    PROFILE_SCOPE_DEFAULT,
)
from custom_components.horticulture_assistant.utils.entry_helpers import (
    entry_device_identifier,
    profile_device_identifier,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

sys.modules["custom_components.horticulture_assistant.__init__"] = hca_module


class _DeviceRegistryProbe:
    def __init__(self) -> None:
        self.creates: list[tuple[str | None, set[tuple[str, str]], dict[str, object]]] = []

    async def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
        if isinstance(identifiers, set):
            ident_iterable = identifiers
        elif identifiers is None:
            ident_iterable = set()
        else:
            ident_iterable = set(identifiers)
        normalised: set[tuple[str, str]] = set()
        for item in ident_iterable:
            if isinstance(item, tuple) and len(item) == 2:
                normalised.add((str(item[0]), str(item[1])))
        self.creates.append((config_entry_id, normalised, kwargs))
        return types.SimpleNamespace(
            id=f"device_{len(self.creates)}",
            identifiers=normalised,
            config_entries={config_entry_id} if config_entry_id else set(),
            name=kwargs.get("name"),
        )

    async def async_remove_device(self, *_args, **_kwargs):  # pragma: no cover - helper
        return None

    def async_get_device(self, identifiers):  # pragma: no cover - helper
        ident_set: set[tuple[str, str]] = set()
        if isinstance(identifiers, set | list | tuple):
            for item in identifiers:
                if isinstance(item, tuple) and len(item) == 2:
                    ident_set.add((str(item[0]), str(item[1])))
        for _entry_id, stored, kwargs in reversed(self.creates):
            if stored & ident_set:
                return types.SimpleNamespace(
                    identifiers=stored,
                    config_entries={_entry_id} if _entry_id else set(),
                    name=kwargs.get("name"),
                )
        return None


@pytest.mark.asyncio
async def test_entry_devices_registered_when_setup_aborts(hass, enable_custom_integrations, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "mint",
            CONF_PLANT_NAME: "Mint",
        },
        options={
            CONF_PROFILES: {
                "mint": {
                    "name": "Mint",
                    "plant_id": "mint",
                    "general": {
                        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
                        "display_name": "Mint",
                    },
                    "sensors": {"moisture": "sensor.soil"},
                }
            }
        },
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)

    registry_probe = _DeviceRegistryProbe()

    monkeypatch.setattr(
        "custom_components.horticulture_assistant.ensure_local_data_paths",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.async_setup_dataset_health",
        AsyncMock(return_value=None),
    )

    with (
        patch(
            "custom_components.horticulture_assistant.ChatApi",
            side_effect=RuntimeError("api initialisation failed"),
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
            return_value=registry_probe,
        ),
        pytest.raises(RuntimeError),
    ):
        await async_setup_entry(hass, entry)

    stored = hass.data[DOMAIN][entry.entry_id]
    stored_map = stored if isinstance(stored, dict) else vars(stored)
    assert stored_map["profiles"]["mint"]["name"] == "Mint"

    identifier = profile_device_identifier(entry.entry_id, "mint")
    assert any(identifier in record[1] for record in registry_probe.creates)


@pytest.mark.asyncio
async def test_successful_setup_registers_devices_and_manage_profiles(hass, enable_custom_integrations, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "mint",
            CONF_PLANT_NAME: "Mint",
        },
        options={
            "sensors": {"moisture": "sensor.soil"},
            CONF_PROFILES: {
                "mint": {
                    "name": "Mint",
                    "plant_id": "mint",
                    "general": {
                        "display_name": "Mint",
                        CONF_PLANT_TYPE: "Herb",
                        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
                    },
                    "sensors": {"moisture": "sensor.soil"},
                }
            },
        },
        entry_id="entry-mint",
        title="Mint",
    )
    entry.add_to_hass(hass)

    registry_probe = _DeviceRegistryProbe()

    fake_local_store = types.SimpleNamespace(
        load=AsyncMock(return_value=None),
        data={"recommendation": {}},
    )
    fake_profile_store = types.SimpleNamespace(async_init=AsyncMock(return_value=None))
    fake_profile_registry = types.SimpleNamespace(
        async_initialize=AsyncMock(return_value=None),
        attach_cloud_publisher=MagicMock(),
        collect_onboarding_warnings=lambda: [],
    )
    fake_cloud_sync_manager = types.SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        status=lambda: {"configured": True, "enabled": True},
        register_token_listener=MagicMock(),
    )
    fake_coordinator = types.SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(return_value=None),
        update_from_entry=MagicMock(),
    )

    with (
        patch(
            "custom_components.horticulture_assistant.ensure_local_data_paths",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.horticulture_assistant.async_setup_dataset_health",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.horticulture_assistant.LocalStore",
            return_value=fake_local_store,
        ),
        patch(
            "custom_components.horticulture_assistant.ProfileStore",
            return_value=fake_profile_store,
        ),
        patch(
            "custom_components.horticulture_assistant.ProfileRegistry",
            return_value=fake_profile_registry,
        ),
        patch(
            "custom_components.horticulture_assistant.CloudSyncManager",
            return_value=fake_cloud_sync_manager,
        ),
        patch(
            "custom_components.horticulture_assistant.CloudSyncPublisher",
            return_value=object(),
        ),
        patch(
            "custom_components.horticulture_assistant.ChatApi",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.horticulture_assistant.HorticultureCoordinator",
            return_value=fake_coordinator,
        ),
        patch(
            "custom_components.horticulture_assistant.HortiAICoordinator",
            return_value=object(),
        ),
        patch(
            "custom_components.horticulture_assistant.HortiLocalCoordinator",
            return_value=object(),
        ),
        patch(
            "custom_components.horticulture_assistant.async_register_http_views",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.horticulture_assistant.ensure_entities_exist",
            MagicMock(),
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
            return_value=registry_probe,
        ),
        patch(
            "custom_components.horticulture_assistant.ensure_all_profile_devices_registered",
            AsyncMock(return_value=None),
        ) as ensure_all,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True

    entry_identifier = entry_device_identifier(entry.entry_id)
    profile_identifier = profile_device_identifier(entry.entry_id, "mint")
    created_sets = [identifiers for _entry_id, identifiers, _ in registry_probe.creates]
    assert any(entry_identifier in identifiers for identifiers in created_sets)
    assert any(profile_identifier in identifiers for identifiers in created_sets)

    options_flow = OptionsFlow(entry)
    options_flow.hass = hass
    menu = await options_flow.async_step_init()
    assert "manage_profiles" in menu["menu_options"]

    manage = await options_flow.async_step_manage_profiles()
    selector = manage["data_schema"].schema.get("profile_id")
    assert isinstance(selector, vol.In)
    assert selector.container.get("mint") == "Mint"

    assert ensure_all.await_count >= 1
    first_call = ensure_all.await_args_list[0]
    assert first_call.args[:2] == (hass, entry)
    assert isinstance(first_call.kwargs["snapshot"], Mapping)
    assert first_call.kwargs["extra_profiles"] == entry.options[CONF_PROFILES]


@pytest.mark.asyncio
async def test_update_listener_resyncs_profile_devices(hass, enable_custom_integrations, tmp_path):
    hass.config.path = lambda *parts: str(tmp_path.joinpath(*parts))

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_PLANT_ID: "mint",
            CONF_PLANT_NAME: "Mint",
        },
        options={},
        entry_id="entry-mint",
    )
    entry.add_to_hass(hass)

    hass.config_entries.async_setup_platforms = AsyncMock(return_value=None)

    update_callback: dict[str, Any] = {}

    def _capture_update_listener(*args):
        if len(args) == 1:
            update_callback["callback"] = args[0]
        elif len(args) >= 2:
            update_callback["callback"] = args[1]
        else:  # pragma: no cover - defensive guard
            raise AssertionError("unexpected listener signature")
        return lambda: None

    entry.add_update_listener = MagicMock(side_effect=_capture_update_listener)
    entry.async_on_unload = AsyncMock(return_value=None)

    initial_snapshot = {
        "plant_id": "mint",
        "plant_name": "Mint",
        "primary_profile_id": "mint",
        "primary_profile_name": "Mint",
        "profiles": {},
    }
    initial_entry_data = {
        "config_entry": entry,
        "snapshot": initial_snapshot,
        "profiles": {},
        "profile_devices": {},
        "profile_ids": [],
    }

    updated_snapshot = {
        **initial_snapshot,
        "profiles": {"mint": {"name": "Mint"}},
    }
    updated_entry_data = {
        "config_entry": entry,
        "snapshot": updated_snapshot,
        "profiles": {"mint": {"name": "Mint"}},
        "profile_devices": {"mint": {"name": "Mint"}},
        "profile_ids": ["mint"],
    }

    update_calls = 0

    async def _store_entry_data(hass_arg, entry_arg):
        hass_arg.data.setdefault(DOMAIN, {})[entry_arg.entry_id] = initial_entry_data
        return initial_entry_data

    async def _update_entry_data(hass_arg, entry_arg, **_kwargs):
        nonlocal update_calls
        update_calls += 1
        if update_calls == 1:
            hass_arg.data.setdefault(DOMAIN, {})[entry_arg.entry_id] = initial_entry_data
            return initial_entry_data
        hass_arg.data.setdefault(DOMAIN, {})[entry_arg.entry_id] = updated_entry_data
        return updated_entry_data

    fake_local_store = types.SimpleNamespace(
        load=AsyncMock(return_value=None),
        data={"recommendation": {}},
    )
    fake_profile_store = types.SimpleNamespace(async_init=AsyncMock(return_value=None))
    fake_profile_registry = types.SimpleNamespace(
        async_initialize=AsyncMock(return_value=None),
        attach_cloud_publisher=MagicMock(),
        collect_onboarding_warnings=lambda: [],
    )
    fake_cloud_sync_manager = types.SimpleNamespace(
        async_start=AsyncMock(return_value=None),
        status=lambda: {"configured": True, "enabled": True},
        register_token_listener=MagicMock(),
    )
    fake_coordinator = types.SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(return_value=None),
        update_from_entry=MagicMock(),
    )

    with (
        patch(
            "custom_components.horticulture_assistant.ensure_local_data_paths",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.horticulture_assistant.async_setup_dataset_health",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.horticulture_assistant.LocalStore",
            return_value=fake_local_store,
        ),
        patch(
            "custom_components.horticulture_assistant.ProfileStore",
            return_value=fake_profile_store,
        ),
        patch(
            "custom_components.horticulture_assistant.ProfileRegistry",
            return_value=fake_profile_registry,
        ),
        patch(
            "custom_components.horticulture_assistant.CloudSyncManager",
            return_value=fake_cloud_sync_manager,
        ),
        patch(
            "custom_components.horticulture_assistant.CloudSyncPublisher",
            return_value=object(),
        ),
        patch(
            "custom_components.horticulture_assistant.ChatApi",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.horticulture_assistant.HorticultureCoordinator",
            return_value=fake_coordinator,
        ),
        patch(
            "custom_components.horticulture_assistant.HortiAICoordinator",
            return_value=object(),
        ),
        patch(
            "custom_components.horticulture_assistant.HortiLocalCoordinator",
            return_value=object(),
        ),
        patch(
            "custom_components.horticulture_assistant.async_register_http_views",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.horticulture_assistant.ensure_entities_exist",
            MagicMock(),
        ),
        patch(
            "custom_components.horticulture_assistant.ha_services.async_register_all",
            AsyncMock(return_value=(True, None)),
        ),
        patch(
            "custom_components.horticulture_assistant.ha_services.async_setup_services",
            AsyncMock(return_value=True),
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.dr.async_get",
            return_value=None,
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.store_entry_data",
            side_effect=_store_entry_data,
        ),
        patch(
            "custom_components.horticulture_assistant.utils.entry_helpers.update_entry_data",
            side_effect=_update_entry_data,
        ),
        patch(
            "custom_components.horticulture_assistant.ensure_all_profile_devices_registered",
            AsyncMock(),
        ) as ensure_mock,
    ):
        assert await async_setup_entry(hass, entry)

        callback = update_callback.get("callback")
        assert callback is not None

        entry.options = {
            CONF_PROFILES: {
                "mint": {"name": "Mint"},
            }
        }

        ensure_mock.reset_mock()

        await callback(hass, entry)

        ensure_mock.assert_called_once()
        kwargs = ensure_mock.call_args.kwargs
        assert kwargs["extra_profiles"] == entry.options[CONF_PROFILES]
        snapshot_payload = kwargs["snapshot"]
        assert isinstance(snapshot_payload, dict)
        assert snapshot_payload.get("profiles", {}).get("mint", {}).get("name") == "Mint"
