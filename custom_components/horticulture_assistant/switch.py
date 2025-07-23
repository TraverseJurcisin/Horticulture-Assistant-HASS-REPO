"""Switch platform for Horticulture Assistant."""

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for irrigation and fertigation control."""
    plant_id = entry.entry_id
    plant_name = f"Plant {plant_id[:6]}"

    entities = [
        IrrigationSwitch(hass, plant_name, plant_id),
        FertigationSwitch(hass, plant_name, plant_id)
    ]
    async_add_entities(entities)

class HorticultureBaseSwitch(SwitchEntity):
    """Base class for horticulture switches."""

    def __init__(self, hass: HomeAssistant, plant_name: str, plant_id: str):
        self.hass = hass
        self._plant_name = plant_name
        self._plant_id = plant_id
        self._attr_has_entity_name = True
        self._attr_is_on = False  # Optimistic switch model

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._plant_id)},
            "name": self._plant_name,
            "manufacturer": "Horticulture Assistant",
            "model": "Irrigation/Fertigation Controller"
        }

    async def async_turn_on(self, **kwargs):
        self._attr_is_on = True
        _LOGGER.info("Turned ON %s for %s", self.name, self._plant_name)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        _LOGGER.info("Turned OFF %s for %s", self.name, self._plant_name)
        self.async_write_ha_state()

class IrrigationSwitch(HorticultureBaseSwitch):
    """Switch to enable or disable irrigation per plant."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Irrigation Control"
        self._attr_unique_id = f"{plant_id}_irrigation_switch"
        self._attr_icon = "mdi:sprinkler"
        self._attr_entity_category = "control"

class FertigationSwitch(HorticultureBaseSwitch):
    """Switch to enable or disable fertigation pump per plant."""

    def __init__(self, hass, plant_name, plant_id):
        super().__init__(hass, plant_name, plant_id)
        self._attr_name = "Fertigation Control"
        self._attr_unique_id = f"{plant_id}_fertigation_switch"
        self._attr_icon = "mdi:beaker-plus"
        self._attr_entity_category = "control"
