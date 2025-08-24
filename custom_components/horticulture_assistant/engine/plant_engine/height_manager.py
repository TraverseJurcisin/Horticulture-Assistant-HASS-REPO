"""Helpers for plant height estimation based on growth stage."""

from __future__ import annotations

from functools import cache

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "plants/plant_height_ranges.json"

_DATA: dict[str, dict[str, tuple[float, float]]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_height_range", "estimate_height"]


def list_supported_plants() -> list[str]:
    """Return plant types with height range data."""
    return list_dataset_entries(_DATA)


@cache
def get_height_range(plant_type: str, stage: str) -> tuple[float, float] | None:
    """Return (min_cm, max_cm) height for ``plant_type`` at ``stage``."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return None
    values = plant.get(normalize_key(stage))
    if isinstance(values, list | tuple) and len(values) == 2:
        try:
            low, high = float(values[0]), float(values[1])
            return low, high
        except (TypeError, ValueError):
            return None
    return None


def estimate_height(
    plant_type: str,
    stage: str,
    progress_pct: float,
) -> float | None:
    """Return estimated plant height in centimeters."""
    if not 0 <= progress_pct <= 100:
        raise ValueError("progress_pct must be between 0 and 100")
    rng = get_height_range(plant_type, stage)
    if not rng:
        return None
    low, high = rng
    return round(low + (high - low) * (progress_pct / 100.0), 1)
