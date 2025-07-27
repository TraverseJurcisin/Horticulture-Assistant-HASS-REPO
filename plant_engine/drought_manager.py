"""Access drought tolerance guidelines for scheduling irrigation."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "drought_tolerance.json"

_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_drought_tolerance",
    "recommend_watering_interval",
]


def list_supported_plants() -> list[str]:
    """Return plant types with drought tolerance data."""
    return list_dataset_entries(_DATA)


@lru_cache(maxsize=None)
def get_drought_tolerance(plant_type: str) -> Dict[str, object] | None:
    """Return drought tolerance info for ``plant_type`` if available."""
    return _DATA.get(normalize_key(plant_type))


def recommend_watering_interval(plant_type: str, default_days: int = 1) -> int:
    """Return maximum days between watering based on drought tolerance."""
    info = get_drought_tolerance(plant_type)
    if not info:
        return default_days
    try:
        days = int(info.get("max_dry_days", default_days))
        return days if days > 0 else default_days
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return default_days
