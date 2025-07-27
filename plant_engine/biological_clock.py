"""Species-conditioned biological clock reset utilities."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, list_dataset_entries, normalize_key

DATA_FILE = "biological_clock_resets.json"

@lru_cache(maxsize=None)
def _data() -> Dict[str, Dict[str, float]]:
    return load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_clock_reset_info",
    "check_clock_reset",
    "format_reset_message",
]


def list_supported_plants() -> list[str]:
    """Return plant types with biological clock reset data."""
    return list_dataset_entries(_data())


def get_clock_reset_info(plant_type: str) -> Dict[str, float] | None:
    """Return reset thresholds for ``plant_type`` if available."""
    return _data().get(normalize_key(plant_type))


def check_clock_reset(
    plant_type: str,
    chilling_hours: float = 0.0,
    drought_days: int = 0,
    photoperiod_hours: float = 0.0,
) -> bool:
    """Return ``True`` if accumulated conditions trigger a clock reset."""
    info = get_clock_reset_info(plant_type)
    if not info:
        return False

    chill_req = info.get("chilling_hours")
    if chill_req is not None and chilling_hours < float(chill_req):
        return False

    drought_req = info.get("drought_days")
    if drought_req is not None and drought_days < int(drought_req):
        return False

    photo_req = info.get("photoperiod_hours")
    if photo_req is not None and photoperiod_hours < float(photo_req):
        return False

    return True


def format_reset_message(
    plant_name: str,
    plant_type: str,
    chilling_hours: float = 0.0,
    drought_days: int = 0,
    photoperiod_hours: float = 0.0,
) -> str:
    """Return human-friendly clock reset message if triggered."""
    if check_clock_reset(plant_type, chilling_hours, drought_days, photoperiod_hours):
        return (
            f"{plant_name} chilling requirement satisfied. Begin ramp-up for spring emergence."
        )
    return f"{plant_name} has not met biological clock reset thresholds."
