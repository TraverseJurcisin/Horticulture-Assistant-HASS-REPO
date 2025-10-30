from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from numbers import Integral, Real
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

_FALLBACK_CACHE: dict[str, dict[str, Any]] = {}


class _InMemoryStore:
    """Fallback storage used when Home Assistant isn't available."""

    async def async_load(self) -> dict[str, dict[str, Any]]:
        return {k: deepcopy(v) for k, v in _FALLBACK_CACHE.items()}

    async def async_save(self, data: Mapping[str, dict[str, Any]]) -> None:
        _FALLBACK_CACHE.clear()
        _FALLBACK_CACHE.update({k: deepcopy(v) for k, v in data.items()})


_IN_MEMORY_STORE = _InMemoryStore()


def _store(hass: HomeAssistant | None) -> Store | _InMemoryStore:
    if hass is None:
        return _IN_MEMORY_STORE
    return Store(hass, STORE_VERSION, STORE_KEY)


def _resolve_cache(hass: HomeAssistant | None) -> dict[str, dict[str, Any]]:
    if hass is not None:
        hass_data = getattr(hass, "data", None)
        if isinstance(hass_data, dict):
            return hass_data.setdefault(_CACHE_KEY, {})
    return _FALLBACK_CACHE


def _normalise_metadata_value(value: Any) -> str | None:
    """Return a string representation for preserved metadata keys."""

    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return str(int(value))
    if isinstance(value, Real):
        number = float(value)
        if not isfinite(number):
            return None
        return format(number, "g")
    return None


async def async_load_all(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    raw = await _store(hass).async_load()
    data = dict(raw) if isinstance(raw, Mapping) else None
    cache = _resolve_cache(hass)
    if data is not None:
        if hass is None and not data and cache:
            return {k: deepcopy(v) for k, v in cache.items()}
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
            normalised = _normalise_metadata_value(raw.get(key))
            if normalised is not None:
                preserved[key] = normalised

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
    cache = _resolve_cache(hass)
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
    await async_save_profile(hass, profile.to_json())


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
        cache = _resolve_cache(hass)
        cache.clear()
        cache.update({k: deepcopy(v) for k, v in data.items()})
        await _store(hass).async_save(data)
