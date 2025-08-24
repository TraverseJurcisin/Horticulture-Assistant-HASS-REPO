from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .store import async_get_profile, async_load_all


async def async_export_profiles(hass: HomeAssistant, path: str | Path) -> Path:
    """Export all stored profiles to a JSON file at ``path``.

    The ``path`` is resolved relative to the Home Assistant configuration
    directory. The output is a UTF-8 encoded file containing a JSON object
    keyed by profile ID. Any parent directories are created automatically.
    """
    import json

    data: dict[str, Any] = await async_load_all(hass)
    out_path = Path(hass.config.path(str(path)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return out_path


async def async_export_profile(
    hass: HomeAssistant, plant_id: str, path: str | Path
) -> Path:
    """Export a single stored profile to a JSON file at ``path``."""
    import json

    profile = await async_get_profile(hass, plant_id)
    if profile is None:
        raise ValueError(f"Unknown profile: {plant_id}")

    out_path = Path(hass.config.path(str(path)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
    return out_path
