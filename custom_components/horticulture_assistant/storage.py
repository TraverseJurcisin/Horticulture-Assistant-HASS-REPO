from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from copy import deepcopy
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


def _clone_default(value: Any) -> Any:
    """Return a new mutable default instance when required."""

    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    return value


class LocalStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict[str, Any] | None = None

    async def load(self) -> dict[str, Any]:
        data = await self._store.async_load()
        if not data:
            data = deepcopy(DEFAULT_DATA)
        else:
            for key, default_value in DEFAULT_DATA.items():
                if key not in data:
                    data[key] = _clone_default(default_value)
                    continue

                current = data[key]

                if isinstance(default_value, dict):
                    if not isinstance(current, Mapping):
                        data[key] = _clone_default(default_value)
                    elif not isinstance(current, dict):
                        data[key] = dict(current)
                elif isinstance(default_value, list):
                    if not isinstance(current, Sequence) or isinstance(current, str | bytes | bytearray):
                        data[key] = _clone_default(default_value)
                    elif not isinstance(current, list):
                        data[key] = list(current)
                elif isinstance(default_value, str):
                    if not isinstance(current, str):
                        data[key] = default_value
                elif current is None:
                    data[key] = default_value
        self.data = data
        return data

    async def save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self.data = data
        elif self.data is None:
            self.data = deepcopy(DEFAULT_DATA)
        async with _LOCK:
            await self._store.async_save(self.data)
