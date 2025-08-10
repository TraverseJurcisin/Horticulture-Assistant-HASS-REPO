from __future__ import annotations
import asyncio
from homeassistant.helpers.storage import Store

STORAGE_KEY = "horticulture_assistant.data"
STORAGE_VERSION = 2

DEFAULT_DATA: dict = {
    "recipes": [],
    "inventory": {},
    "history": [],
    "profile": {},
    "recommendation": "",
}


class LocalStore:
    def __init__(self, hass):
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.data: dict | None = None
        self._lock = asyncio.Lock()

    async def load(self) -> dict:
        data = await self._store.async_load()
        if not data:
            data = DEFAULT_DATA.copy()
        else:
            if data.get("version") == 1:
                data = migrate_v1_to_v2(data)
            for key, value in DEFAULT_DATA.items():
                data.setdefault(key, value.copy() if isinstance(value, (dict, list)) else value)
        self.data = data
        return data

    async def save(self, data: dict | None = None) -> None:
        if data is not None:
            self.data = data
        elif self.data is None:
            self.data = DEFAULT_DATA.copy()
        async with self._lock:
            await self._store.async_save(self.data)


def migrate_v1_to_v2(data: dict) -> dict:
    """Migrate old v1 layout to v2."""
    plants = data.pop("plant_registry", data.pop("plants", {}))
    zones = data.pop("zones_registry", data.pop("zones", {}))
    data["plants"] = plants
    data["zones"] = zones
    data["version"] = 2
    return data
