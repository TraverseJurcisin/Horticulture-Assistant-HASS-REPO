"""Helpers for canopy area lookups."""

from __future__ import annotations

from functools import cache

from .plant_density import get_spacing_cm
from .utils import load_dataset, normalize_key

DATA_FILE = "stages/canopy_area.json"

_DATA: dict[str, dict[str, float]] = load_dataset(DATA_FILE)

__all__ = ["get_canopy_area", "estimate_canopy_area"]


@cache
def get_canopy_area(plant_type: str, stage: str | None = None) -> float | None:
    """Return canopy area for ``plant_type`` and ``stage`` if defined."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return None
    if stage:
        val = plant.get(normalize_key(stage))
        if isinstance(val, int | float):
            return float(val)
    default = plant.get("default")
    return float(default) if isinstance(default, int | float) else None


def estimate_canopy_area(plant_type: str, stage: str | None = None) -> float:
    """Return canopy area using dataset or spacing guidelines."""
    area = get_canopy_area(plant_type, stage)
    if area is not None:
        return area
    spacing = get_spacing_cm(plant_type)
    if spacing is not None and spacing > 0:
        return round((spacing / 100) ** 2, 3)
    return 0.25
