"""Switch platform for Horticulture Assistant."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_CONTROL, DOMAIN
from .entity_base import HorticultureBaseEntity
from .utils.entry_helpers import get_entry_data, store_entry_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for irrigation and fertigation control."""
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    plant_id = stored["plant_id"]
    plant_name = stored["plant_name"]

    entities = [
        IrrigationSwitch(hass, entry.entry_id, plant_name, plant_id),
        FertigationSwitch(hass, entry.entry_id, plant_name, plant_id),
    ]
    async_add_entities(entities)


class HorticultureBaseSwitch(HorticultureBaseEntity, SwitchEntity):
    """Base class for horticulture switches."""

    def __init__(
        self, hass: HomeAssistant, entry_id: str, plant_name: str, plant_id: str
    ) -> None:
        super().__init__(
            plant_name, plant_id, model="Irrigation/Fertigation Controller"
        )
        self.hass = hass
        self._entry_id = entry_id
        self._attr_is_on = False  # Optimistic switch model

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        if not self._attr_is_on:
            self._attr_is_on = True
            try:
                self.async_write_ha_state()
            except Exception as err:  # Log unexpected state update errors
                _LOGGER.error("Failed to update state for %s: %s", self.entity_id, err)
            _LOGGER.info("Turned ON %s for %s", self.name, self._plant_name)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        if self._attr_is_on:
            self._attr_is_on = False
            try:
                self.async_write_ha_state()
            except Exception as err:
                _LOGGER.error("Failed to update state for %s: %s", self.entity_id, err)
            _LOGGER.info("Turned OFF %s for %s", self.name, self._plant_name)


class IrrigationSwitch(HorticultureBaseSwitch):
    """Switch to enable or disable irrigation per plant."""

    def __init__(self, hass, entry_id, plant_name, plant_id):
        super().__init__(hass, entry_id, plant_name, plant_id)
        self._attr_name = "Irrigation Control"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{plant_id}_irrigation_switch"
        self._attr_icon = "mdi:sprinkler"
        self._attr_entity_category = CATEGORY_CONTROL


class FertigationSwitch(HorticultureBaseSwitch):
    """Switch to enable or disable fertigation pump per plant."""

    def __init__(self, hass, entry_id, plant_name, plant_id):
        super().__init__(hass, entry_id, plant_name, plant_id)
        self._attr_name = "Fertigation Control"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{plant_id}_fertigation_switch"
        self._attr_icon = "mdi:beaker-plus"
        self._attr_entity_category = CATEGORY_CONTROL
