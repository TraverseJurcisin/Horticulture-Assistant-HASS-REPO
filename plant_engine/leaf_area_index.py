"""Leaf Area Index dataset helpers."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key
from .canopy import estimate_canopy_area

DATA_FILE = "leaf_area_index.json"

_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = ["get_leaf_area_index", "estimate_leaf_area_index"]


@lru_cache(maxsize=None)
def get_leaf_area_index(plant_type: str, stage: str | None = None) -> float | None:
    """Return leaf area index for ``plant_type`` and ``stage`` if defined."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return None
    if stage:
        val = plant.get(normalize_key(stage))
        if isinstance(val, (int, float)):
            return float(val)
    default = plant.get("default")
    return float(default) if isinstance(default, (int, float)) else None


def estimate_leaf_area_index(plant_type: str, stage: str | None = None) -> float:
    """Return LAI using dataset or approximate from canopy area."""
    lai = get_leaf_area_index(plant_type, stage)
    if lai is not None:
        return lai
    area = estimate_canopy_area(plant_type, stage)
    return round(area * 3, 2)
