from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from ..const import CONF_PROFILES
from .options import options_profile_to_dataclass
from .schema import BioProfile
from .utils import link_species_and_cultivars, normalise_profile_payload

STORE_VERSION = 1
STORE_KEY = "horticulture_assistant_profiles"

_CACHE_KEY = "horticulture_assistant.profile_store_cache"
CACHE_KEY = _CACHE_KEY


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORE_VERSION, STORE_KEY)


async def async_load_all(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    data = await _store(hass).async_load() or {}
    cache = hass.data.setdefault(_CACHE_KEY, {})
    if data:
        cache.clear()
        cache.update({k: deepcopy(v) for k, v in data.items()})
        return data
    if cache:
        return {k: deepcopy(v) for k, v in cache.items()}
    return {}


async def async_save_profile(hass: HomeAssistant | None, profile: BioProfile | dict[str, Any]) -> None:
    """Persist a profile dictionary or dataclass to storage."""

    preserved: dict[str, Any] = {}

    if isinstance(profile, BioProfile):
        profile_obj = profile
    else:
        raw: dict[str, Any] = dict(profile)

        for key in ("species_display", "species_pid", "image_url"):
            value = raw.get(key)
            if isinstance(value, str) and value:
                preserved[key] = value

        credentials = raw.get("opb_credentials")
        if isinstance(credentials, Mapping):
            preserved["opb_credentials"] = deepcopy(dict(credentials))

        candidate_id = raw.get("plant_id") or raw.get("profile_id") or raw.get("name") or "profile"
        fallback_id = str(candidate_id)
        display_name = raw.get("display_name") or raw.get("name") or fallback_id
        normalised = normalise_profile_payload(raw, fallback_id=fallback_id, display_name=display_name)
        profile_obj = BioProfile.from_json(normalised)

    payload = profile_obj.to_json()

    if preserved:
        payload.update(preserved)

    data = await async_load_all(hass)
    data[payload["plant_id"]] = payload
    if hass is not None:
        hass_data = getattr(hass, "data", None)
        if isinstance(hass_data, dict):
            cache = hass_data.setdefault(_CACHE_KEY, {})
            cache.clear()
            cache.update({k: deepcopy(v) for k, v in data.items()})
    await _store(hass).async_save(data)


async def async_save_profile_from_options(hass: HomeAssistant, entry, profile_id: str) -> None:
    """Persist a profile from config entry options to storage."""

    prof = entry.options.get(CONF_PROFILES, {}).get(profile_id, {})
    profile = options_profile_to_dataclass(
        profile_id,
        prof,
        display_name=prof.get("name") or profile_id,
    )
    await async_save_profile(hass, profile)


async def async_get_profile(hass: HomeAssistant, plant_id: str) -> dict[str, Any] | None:
    return (await async_load_all(hass)).get(plant_id)


async def async_load_profile(hass: HomeAssistant, plant_id: str) -> BioProfile | None:
    """Load a BioProfile dataclass for a given plant ID."""

    data = await async_get_profile(hass, plant_id)
    return BioProfile.from_json(data) if data else None


async def async_load_profiles(hass: HomeAssistant) -> dict[str, BioProfile]:
    """Load all stored profiles as dataclasses."""

    data = await async_load_all(hass)
    profiles = {pid: BioProfile.from_json(p) for pid, p in data.items()}
    link_species_and_cultivars(profiles.values())
    return profiles


async def async_delete_profile(hass: HomeAssistant, plant_id: str) -> None:
    data = await async_load_all(hass)
    if plant_id in data:
        del data[plant_id]
        cache = hass.data.setdefault(_CACHE_KEY, {})
        cache.clear()
        cache.update({k: deepcopy(v) for k, v in data.items()})
        await _store(hass).async_save(data)
