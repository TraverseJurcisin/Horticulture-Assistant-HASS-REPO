from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .store import async_save_profile


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
        data: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as err:  # pragma: no cover - edge case
        raise ValueError(f"Invalid profile JSON: {err}") from err
    count = 0
    for profile in data.values():
        await async_save_profile(hass, profile)
        count += 1
    return count
