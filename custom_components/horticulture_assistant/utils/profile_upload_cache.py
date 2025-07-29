from __future__ import annotations

import json
import logging
from pathlib import Path

try:
    from homeassistant.core import HomeAssistant
except ImportError:  # pragma: no cover - allow tests without HA installed
    HomeAssistant = None  # type: ignore

from .path_utils import plants_path, ensure_data_dir

_LOGGER = logging.getLogger(__name__)

__all__ = ["cache_profile_for_upload"]


def _load_section(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - unexpected I/O errors
        _LOGGER.error("Failed reading %s: %s", path, exc)
        return None


def cache_profile_for_upload(plant_id: str, hass: HomeAssistant | None = None) -> None:
    """Cache a combined profile JSON for later upload."""
    plant_dir = Path(plants_path(hass, plant_id))
    cache_dir = Path(ensure_data_dir(hass, "profile_cache"))

    profile = {}
    for fname in (
        "general.json",
        "environment.json",
        "nutrition.json",
        "irrigation.json",
        "stages.json",
    ):
        section = _load_section(plant_dir / fname)
        if section is not None:
            profile[fname[:-5]] = section

    if not profile:
        _LOGGER.warning("No profile data found for %s; nothing cached", plant_id)
        return

    out = cache_dir / f"{plant_id}.json"
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        _LOGGER.info("Cached profile for %s at %s", plant_id, out)
    except Exception as exc:  # pragma: no cover - unexpected I/O errors
        _LOGGER.error("Failed to cache profile %s: %s", plant_id, exc)
