from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

STORAGE_KEY = "horticulture_assistant.data"
STORAGE_VERSION = 2
_LOCK = asyncio.Lock()

DEFAULT_DATA: dict[str, Any] = {
    "recipes": [],
    "inventory": {},
    "history": [],
    "plants": {},
    "profile": {},
    "recommendation": "",
    "zones": {},
}


class LocalStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] | None = None

    async def load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        if not data:
            data = DEFAULT_DATA.copy()
        else:
            for key, value in DEFAULT_DATA.items():
                data.setdefault(key, value.copy() if isinstance(value, dict | list) else value)
        self.data = data
        return data

    async def save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self.data = data
        elif self.data is None:
            self.data = DEFAULT_DATA.copy()
        async with _LOCK:
            await self._store.async_save(self.data)
