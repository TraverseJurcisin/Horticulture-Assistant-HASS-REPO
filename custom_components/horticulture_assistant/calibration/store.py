from __future__ import annotations

from typing import Any

try:  # pragma: no cover - allow import without Home Assistant
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.storage import Store
except Exception:  # pragma: no cover
    HomeAssistant = Any  # type: ignore

    class Store:  # type: ignore
        def __init__(self, *args, **kwargs):
            self._data = {}

        async def async_load(self):  # noqa: D401 - mimic HA Store
            return self._data

        async def async_save(self, data):  # noqa: D401 - mimic HA Store
            self._data = data


STORE_VERSION = 1
STORE_KEY = "horticulture_assistant_calibrations"


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORE_VERSION, STORE_KEY)


async def async_load_all(hass: HomeAssistant) -> dict[str, Any]:
    return await _store(hass).async_load() or {}


async def async_save_for_entity(
    hass: HomeAssistant, lux_entity_id: str, record: dict[str, Any]
) -> None:
    data = await async_load_all(hass)
    data[lux_entity_id] = record
    await _store(hass).async_save(data)


async def async_get_for_entity(hass: HomeAssistant, lux_entity_id: str) -> dict[str, Any] | None:
    return (await async_load_all(hass)).get(lux_entity_id)
