from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .schema import Citation, PlantProfile, VariableValue

STORE_VERSION = 1
STORE_KEY = "horticulture_assistant_profiles"


def _store(hass: HomeAssistant) -> Store:
    return Store(hass, STORE_VERSION, STORE_KEY)


async def async_load_all(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    return await _store(hass).async_load() or {}


async def async_save_profile(
    hass: HomeAssistant, profile: PlantProfile | dict[str, Any]
) -> None:
    """Persist a profile dictionary or dataclass to storage."""

    if isinstance(profile, PlantProfile):
        profile = profile.to_json()

    data = await async_load_all(hass)
    data[profile["plant_id"]] = profile
    await _store(hass).async_save(data)


async def async_save_profile_from_options(
    hass: HomeAssistant, entry, profile_id: str
) -> None:
    """Persist a profile from config entry options to storage."""

    prof = entry.options.get("profiles", {}).get(profile_id, {})
    variables: dict[str, VariableValue] = {}
    for key, value in prof.get("thresholds", {}).items():
        mode = prof.get("sources", {}).get(key, {}).get("mode", "manual")
        cit_data = prof.get("citations", {}).get(key)
        cits: list[Citation] = []
        if cit_data:
            cits.append(
                Citation(
                    source=cit_data.get("mode", mode),
                    title=cit_data.get("source_detail", ""),
                    details={"source_detail": cit_data.get("source_detail", "")},
                    accessed=cit_data.get("ts"),
                )
            )
        variables[key] = VariableValue(value=value, source=mode, citations=cits)

    profile = PlantProfile(
        plant_id=profile_id,
        display_name=prof.get("name", profile_id),
        species=prof.get("species"),
        variables=variables,
        last_resolved=prof.get("last_resolved"),
    )
    await async_save_profile(hass, profile)


async def async_get_profile(hass: HomeAssistant, plant_id: str) -> dict[str, Any] | None:
    return (await async_load_all(hass)).get(plant_id)


async def async_load_profile(
    hass: HomeAssistant, plant_id: str
) -> PlantProfile | None:
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
