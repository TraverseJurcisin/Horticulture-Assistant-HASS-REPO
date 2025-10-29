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

STORE_VERSION = 2
STORE_KEY = "horticulture_assistant_profiles"
STORE_CACHE_KEY = "horticulture_assistant_profile_store"


def _store(hass: HomeAssistant) -> Store:
    cache = getattr(hass, "data", None)
    if isinstance(cache, dict):
        store = cache.get(STORE_CACHE_KEY)
        if store is None:
            store = Store(hass, STORE_VERSION, STORE_KEY)
            cache[STORE_CACHE_KEY] = store
        return store
    return Store(hass, STORE_VERSION, STORE_KEY)


def get_profile_store(hass: HomeAssistant) -> Store:
    """Return the shared Home Assistant storage instance for profiles."""

    return _store(hass)


async def async_load_all(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    raw = await _store(hass).async_load() or {}
    if isinstance(raw, Mapping):
        profiles = raw.get("profiles")
        if isinstance(profiles, Mapping):
            return {
                str(pid): dict(payload)
                for pid, payload in profiles.items()
                if isinstance(pid, str) and isinstance(payload, Mapping)
            }
        return {
            str(pid): dict(payload)
            for pid, payload in raw.items()
            if isinstance(pid, str) and isinstance(payload, Mapping)
        }
    return {}


async def async_save_profile(hass: HomeAssistant, profile: BioProfile | dict[str, Any]) -> None:
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
            preserved["opb_credentials"] = deepcopy(credentials)

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
        await _store(hass).async_save(data)
