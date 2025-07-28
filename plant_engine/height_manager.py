"""Helpers for plant height estimation based on growth stage."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Tuple

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "plant_height_ranges.json"

_DATA: Dict[str, Dict[str, Tuple[float, float]]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_height_range", "estimate_height"]


def list_supported_plants() -> list[str]:
    """Return plant types with height range data."""
    return list_dataset_entries(_DATA)


@lru_cache(maxsize=None)
def get_height_range(plant_type: str, stage: str) -> Tuple[float, float] | None:
    """Return (min_cm, max_cm) height for ``plant_type`` at ``stage``."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return None
    values = plant.get(normalize_key(stage))
    if (
        isinstance(values, (list, tuple))
        and len(values) == 2
    ):
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
