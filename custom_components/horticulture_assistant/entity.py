from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HorticultureCoordinator
from .entity_base import HorticultureBaseEntity
from .utils.entry_helpers import resolve_profile_device_info, resolve_profile_image_url


class HorticultureEntity(HorticultureBaseEntity, CoordinatorEntity[HorticultureCoordinator]):
    """Entity tied to a plant profile."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HorticultureCoordinator, profile_id: str, profile_name: str) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        entry_id = getattr(coordinator, "entry_id", None)
        HorticultureBaseEntity.__init__(
            self,
            entry_id,
            profile_name,
            profile_id,
            model="Plant Profile",
        )
        self._profile_id = profile_id
        self._profile_name = profile_name

    @property
    def device_info(self) -> dict[str, Any]:
        hass = getattr(self, "hass", None)
        if hass:
            info = resolve_profile_device_info(hass, self._entry_id, self._profile_id)
            if info:
                return dict(info)

        return super().device_info

    @property
    def entity_picture(self) -> str | None:
        if not getattr(self, "hass", None):
            return None
        return resolve_profile_image_url(self.hass, self._entry_id, self._profile_id)
