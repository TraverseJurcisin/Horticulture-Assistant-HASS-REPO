"""Shared base classes for Horticulture Assistant entities."""

from __future__ import annotations

from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .utils.entry_helpers import get_entry_data_by_plant_id


class HorticultureBaseEntity(Entity):
    """Common device information for sensors, binary sensors and switches."""

    def __init__(
        self, plant_name: str, plant_id: str, *, model: str = "AI Monitored Plant"
    ) -> None:
        self._plant_name = plant_name
        self._plant_id = plant_id
        self._model = model
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict:
        """Return device information shared across entity types."""
        return {
            "identifiers": {(DOMAIN, f"plant:{self._plant_id}")},
            "name": self._plant_name,
            "manufacturer": "Horticulture Assistant",
            "model": self._model,
        }

    @property
    def entity_picture(self) -> str | None:
        """Return a profile image if configured."""
        if not self.hass:
            return None
        stored = get_entry_data_by_plant_id(self.hass, self._plant_id)
        if not stored:
            return None
        entry = stored.get("config_entry")
        if entry is None:
            return None
        return entry.options.get("image_url")
