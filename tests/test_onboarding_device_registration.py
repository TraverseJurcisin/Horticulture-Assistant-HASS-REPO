import sys
import types
from unittest.mock import AsyncMock, patch

import pytest

import custom_components.horticulture_assistant as hca_module
from custom_components.horticulture_assistant import async_setup_entry
from custom_components.horticulture_assistant.const import (
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    DOMAIN,
    PROFILE_SCOPE_DEFAULT,
)
from custom_components.horticulture_assistant.utils.entry_helpers import (
    profile_device_identifier,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

sys.modules["custom_components.horticulture_assistant.__init__"] = hca_module


class _DeviceRegistryProbe:
    def __init__(self) -> None:
        self.creates: list[tuple[str | None, set[tuple[str, str]], dict[str, object]]] = []

    def async_get_or_create(self, *, identifiers=None, config_entry_id=None, **kwargs):
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
    assert stored["profiles"]["mint"]["name"] == "Mint"

    identifier = profile_device_identifier(entry.entry_id, "mint")
    assert any(identifier in record[1] for record in registry_probe.creates)
