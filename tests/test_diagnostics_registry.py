from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant.const import CONF_PROFILES, DOMAIN
from custom_components.horticulture_assistant.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.horticulture_assistant.profile_registry import ProfileRegistry

pytestmark = pytest.mark.asyncio


async def test_diagnostics_prefers_registry(hass):
    """When a registry is present diagnostics should use it."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_PROFILES: {"p1": {"name": "Plant"}}},
    )
    entry.add_to_hass(hass)
    reg = ProfileRegistry(hass, entry)
    await reg.async_initialize()
    hass.data.setdefault(DOMAIN, {})["profile_registry"] = reg

    with patch(
        "custom_components.horticulture_assistant.diagnostics.async_load_all",
        new_callable=AsyncMock,
    ) as load_all:
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["profiles"]["p1"]["display_name"] == "Plant"
    load_all.assert_not_called()


async def test_diagnostics_falls_back_to_store(hass):
    """If no registry exists diagnostics loads directly from storage."""

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    fake_profiles = {"a": {"variables": {}}}
    with patch(
        "custom_components.horticulture_assistant.diagnostics.async_load_all",
        AsyncMock(return_value=fake_profiles),
    ) as load_all:
        result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["profiles"] == fake_profiles
    load_all.assert_called_once()
