from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .schema import BioProfile
from .store import async_get_profile, async_load_all
from .utils import normalise_profile_payload


def _normalise_payload(payload: Mapping[str, Any], fallback_id: str) -> dict[str, Any]:
    """Return a serialisable payload with structured sections."""

    raw = dict(payload)
    display_name = raw.get("display_name") or raw.get("name") or fallback_id
    normalised = normalise_profile_payload(raw, fallback_id=fallback_id, display_name=display_name)
    profile = BioProfile.from_json(normalised)
    return profile.to_json()


async def async_export_profiles(hass: HomeAssistant, path: str | Path) -> Path:
    """Export all stored profiles to a JSON file at ``path``.

    The ``path`` is resolved relative to the Home Assistant configuration
    directory. The output is a UTF-8 encoded file containing a JSON object
    keyed by profile ID. Any parent directories are created automatically.
    """
    import json

    data: dict[str, Any] = await async_load_all(hass)
    normalised = {pid: _normalise_payload(payload, pid) for pid, payload in data.items()}
    out_path = Path(hass.config.path(str(path)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(normalised, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


async def async_export_profile(hass: HomeAssistant, plant_id: str, path: str | Path) -> Path:
    """Export a single stored profile to a JSON file at ``path``."""
    import json

    profile = await async_get_profile(hass, plant_id)
    if profile is None:
        raise ValueError(f"Unknown profile: {plant_id}")

    out_path = Path(hass.config.path(str(path)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _normalise_payload(profile, plant_id)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path
