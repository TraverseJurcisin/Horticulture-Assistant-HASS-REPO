from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .storage import LocalStore

_LOGGER = logging.getLogger(__name__)


class HortiLocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fast local computations."""

    def __init__(self, hass, store: LocalStore, update_minutes: int):
        super().__init__(
            hass,
            _LOGGER,
            name="horticulture_assistant_local",
            update_interval=timedelta(minutes=update_minutes),
        )
        self.store = store
        self.data = store.data or {}

    async def _async_update_data(self) -> dict[str, Any]:
        return self.store.data or {}
