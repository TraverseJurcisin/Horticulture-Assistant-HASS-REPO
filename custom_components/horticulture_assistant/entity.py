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

        return super().profile_unique_id(key)

    @property
    def available(self) -> bool:
        """Report entities as available while awaiting coordinator data.

        Coordinator entities default to ``unavailable`` until a successful
        refresh completes. For plant profile entities this prevents device
        actions from targeting them immediately after setup. We instead mark
        them as available (yielding an ``unknown`` state because no value is
        set) until the coordinator reports a failure after its first attempt.
        These entities should also stay available even when they have no
        physical/linked sensor so they can be referenced in automations from
        the moment Home Assistant boots.
        """

        if getattr(self, "_attr_available", None) is False:
            return False

        coordinator = getattr(self, "coordinator", None)
        if coordinator is None:
            return True

        if coordinator.last_update_success:
            return True

        return coordinator.last_update_success_time is None
