"""Access drought tolerance guidelines for scheduling irrigation."""

from __future__ import annotations

from functools import cache

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "water/drought_tolerance.json"

_DATA: dict[str, dict[str, object]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_drought_tolerance",
    "recommend_watering_interval",
]


def list_supported_plants() -> list[str]:
    """Return plant types with drought tolerance data."""
    return list_dataset_entries(_DATA)


@cache
def get_drought_tolerance(plant_type: str) -> dict[str, object] | None:
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
