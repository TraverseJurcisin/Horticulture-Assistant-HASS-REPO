from __future__ import annotations

import inspect
import logging
from contextlib import suppress
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

    async def async_shutdown(self) -> None:
        """Cancel scheduled refreshes and drop listeners."""

        if hasattr(self, "async_stop"):
            with suppress(Exception):
                await self.async_stop()

        debounced = getattr(self, "_debounced_refresh", None)
        if debounced is not None:
            with suppress(Exception):
                await debounced.async_cancel()

        unsub = getattr(self, "_unsub_refresh", None)
        if unsub is not None:
            with suppress(Exception):
                result = unsub()
                if inspect.isawaitable(result):
                    await result
            self._unsub_refresh = None

        listeners = getattr(self, "_listeners", None)
        if isinstance(listeners, dict):
            listeners.clear()
