from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .schema import PlantProfile

STORE_VERSION = 1
STORE_KEY = "horticulture_assistant_profiles"


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORE_VERSION, STORE_KEY)


async def async_load_all(hass: HomeAssistant) -> Dict[str, Dict[str, Any]]:
    return await _store(hass).async_load() or {}


async def async_save_profile(
    hass: HomeAssistant, profile: PlantProfile | Dict[str, Any]
) -> None:
    """Persist a profile dictionary or dataclass to storage."""

    if isinstance(profile, PlantProfile):
        profile = profile.to_json()

    data = await async_load_all(hass)
    data[profile["plant_id"]] = profile
    await _store(hass).async_save(data)


async def async_get_profile(hass: HomeAssistant, plant_id: str) -> Optional[Dict[str, Any]]:
    return (await async_load_all(hass)).get(plant_id)


async def async_load_profile(
    hass: HomeAssistant, plant_id: str
) -> Optional[PlantProfile]:
    """Load a PlantProfile dataclass for a given plant ID."""

    data = await async_get_profile(hass, plant_id)
    return PlantProfile.from_json(data) if data else None


async def async_load_profiles(hass: HomeAssistant) -> Dict[str, PlantProfile]:
    """Load all stored profiles as dataclasses."""

    data = await async_load_all(hass)
    return {pid: PlantProfile.from_json(p) for pid, p in data.items()}


async def async_delete_profile(hass: HomeAssistant, plant_id: str) -> None:
    data = await async_load_all(hass)
    if plant_id in data:
        del data[plant_id]
        await _store(hass).async_save(data)
