from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .schema import BioProfile
from .store import async_save_profile
from .utils import normalise_profile_payload


async def async_import_profiles(hass: HomeAssistant, path: str | Path) -> int:
    """Import profiles from a JSON file at ``path``.

    The ``path`` is resolved relative to the Home Assistant configuration
    directory. Existing profiles with the same ID are overwritten.
    Returns the number of profiles imported.
    """
    import json

    in_path = Path(hass.config.path(str(path)))
    text = in_path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:  # pragma: no cover - edge case
        raise ValueError(f"Invalid profile JSON: {err}") from err
    if isinstance(data, dict):
        profiles = list(data.values())
    elif isinstance(data, list):
        profiles = data
    else:
        raise ValueError("Invalid profile JSON: expected object or list")

    count = 0
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ValueError("Invalid profile entry: expected mapping")

        raw: dict[str, Any] = dict(profile)
        candidate_id = raw.get("plant_id") or raw.get("profile_id") or raw.get("name") or "profile"
        fallback_id = str(candidate_id)
        display_name = raw.get("display_name") or raw.get("name") or fallback_id
        normalised = normalise_profile_payload(raw, fallback_id=fallback_id, display_name=display_name)
        profile_obj = BioProfile.from_json(normalised)

        await async_save_profile(hass, profile_obj)
        count += 1
    return count
