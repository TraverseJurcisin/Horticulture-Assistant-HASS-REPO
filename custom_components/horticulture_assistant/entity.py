from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HorticultureCoordinator
from .entity_base import HorticultureBaseEntity


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

    def profile_unique_id(self, key: str | None = None) -> str:
        """Return a stable unique id for profile entities."""

        profile_part = self._profile_id or "profile"
        if key:
            return f"{profile_part}_{key}"
        return profile_part
