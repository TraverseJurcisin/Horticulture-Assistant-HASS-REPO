"""Plant spacing guidelines and density calculations."""

from __future__ import annotations

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "plants/plant_density_guidelines.json"

_DATA: dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_spacing_cm", "plants_per_area"]


def list_supported_plants() -> list[str]:
    """Return plant types with spacing guidelines."""
    return list_dataset_entries(_DATA)


def get_spacing_cm(plant_type: str) -> float | None:
    """Return recommended in-row spacing in centimeters."""
    value = _DATA.get(normalize_key(plant_type))
    return float(value) if isinstance(value, int | float) else None


def plants_per_area(plant_type: str, area_m2: float) -> float | None:
    """Return approximate plant count for ``area_m2`` given spacing."""
    if area_m2 <= 0:
        raise ValueError("area_m2 must be positive")
    spacing = get_spacing_cm(plant_type)
    if spacing is None or spacing <= 0:
        return None
    spacing_m = spacing / 100
    plants = area_m2 / (spacing_m**2)
    return round(plants, 1)
