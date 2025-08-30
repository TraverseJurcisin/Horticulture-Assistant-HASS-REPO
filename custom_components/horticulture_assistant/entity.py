from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HorticultureCoordinator


class HorticultureEntity(CoordinatorEntity[HorticultureCoordinator]):
    """Entity tied to a plant profile."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HorticultureCoordinator, profile_id: str, profile_name: str
    ) -> None:
        super().__init__(coordinator)
        self._profile_id = profile_id
        self._profile_name = profile_name

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"profile:{self._profile_id}")},
            "name": self._profile_name,
            "manufacturer": "Horticulture Assistant",
            "model": "Plant Profile",
        }
