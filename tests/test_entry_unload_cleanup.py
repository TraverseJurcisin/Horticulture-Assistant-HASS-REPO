from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.horticulture_assistant import DOMAIN, async_unload_entry
from pytest_homeassistant_custom_component.common import MockConfigEntry


class _LegacyUnload(SimpleNamespace):
    def __init__(self, result=True):
        super().__init__(calls=[], result=result)

    async def async_forward_entry_unload(self, entry, platform):  # pylint: disable=unused-argument
        self.calls.append(platform)
        return self.result


@pytest.mark.asyncio
async def test_unload_cleans_registry_and_domain_data(hass):
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)  # type: ignore[attr-defined]

    registry_sentinel = object()
    hass.data[DOMAIN] = {
        entry.entry_id: {"profile_registry": registry_sentinel, "dataset_monitor_attached": False},
        "registry": registry_sentinel,
    }

    unload_ok = await async_unload_entry(hass, entry)

    assert unload_ok is True
    assert DOMAIN not in hass.data


@pytest.mark.asyncio
async def test_unload_uses_legacy_unload_when_present(hass):
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    legacy = _LegacyUnload()
    hass.config_entries.async_forward_entry_unload = legacy.async_forward_entry_unload  # type: ignore[attr-defined]
    hass.config_entries.async_unload_platforms = None  # type: ignore[attr-defined]

    hass.data[DOMAIN] = {entry.entry_id: {"dataset_monitor_attached": False}}

    unload_ok = await async_unload_entry(hass, entry)

    assert unload_ok is True
    assert set(legacy.calls) == {"sensor", "binary_sensor", "switch", "number"}
