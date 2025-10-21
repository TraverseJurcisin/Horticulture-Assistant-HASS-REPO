from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .schema import PlantProfile
from .options import options_profile_to_dataclass
from .utils import normalise_profile_payload

STORE_VERSION = 1
STORE_KEY = "horticulture_assistant_profiles"


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORE_VERSION, STORE_KEY)


async def async_load_all(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    return await _store(hass).async_load() or {}


async def async_save_profile(hass: HomeAssistant, profile: PlantProfile | dict[str, Any]) -> None:
    """Persist a profile dictionary or dataclass to storage."""

    if isinstance(profile, PlantProfile):
        profile_obj = profile
    else:
        raw: dict[str, Any] = dict(profile)
        candidate_id = raw.get("plant_id") or raw.get("profile_id") or raw.get("name") or "profile"
        fallback_id = str(candidate_id)
        display_name = raw.get("display_name") or raw.get("name") or fallback_id
        normalised = normalise_profile_payload(raw, fallback_id=fallback_id, display_name=display_name)
        profile_obj = PlantProfile.from_json(normalised)

    payload = profile_obj.to_json()

    data = await async_load_all(hass)
    data[payload["plant_id"]] = payload
    await _store(hass).async_save(data)


async def async_save_profile_from_options(hass: HomeAssistant, entry, profile_id: str) -> None:
    """Persist a profile from config entry options to storage."""

    prof = entry.options.get("profiles", {}).get(profile_id, {})
    profile = options_profile_to_dataclass(
        profile_id,
        prof,
        display_name=prof.get("name") or profile_id,
    )
    await async_save_profile(hass, profile)


async def async_get_profile(hass: HomeAssistant, plant_id: str) -> dict[str, Any] | None:
    return (await async_load_all(hass)).get(plant_id)


async def async_load_profile(hass: HomeAssistant, plant_id: str) -> PlantProfile | None:
    """Load a PlantProfile dataclass for a given plant ID."""

    data = await async_get_profile(hass, plant_id)
    return PlantProfile.from_json(data) if data else None


async def async_load_profiles(hass: HomeAssistant) -> dict[str, PlantProfile]:
    """Load all stored profiles as dataclasses."""

    data = await async_load_all(hass)
    return {pid: PlantProfile.from_json(p) for pid, p in data.items()}


async def async_delete_profile(hass: HomeAssistant, plant_id: str) -> None:
    data = await async_load_all(hass)
    if plant_id in data:
        del data[plant_id]
        await _store(hass).async_save(data)
