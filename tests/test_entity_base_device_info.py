"""Tests for base entity device info fallbacks."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from custom_components.horticulture_assistant.const import DOMAIN
from custom_components.horticulture_assistant.entity_base import HorticultureEntryEntity


@pytest.mark.parametrize("stored_name", [None, "", "   "])
def test_entry_entity_device_info_uses_default_when_name_missing(stored_name: str | None) -> None:
    """Ensure the default name is applied when stored metadata lacks one."""

    hass = HomeAssistant()
    entry_id = "entry-1"
    hass.data.setdefault(DOMAIN, {})[entry_id] = {
        "entry_device_info": {
            "identifiers": {("horticulture_assistant", "entry:entry-1")},
            "name": stored_name,
        }
    }

    entity = HorticultureEntryEntity(entry_id, default_device_name="Plant Entry")
    entity.hass = hass

    info = entity.device_info

    assert info["name"] == "Plant Entry"
