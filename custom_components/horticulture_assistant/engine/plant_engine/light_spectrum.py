"""Helpers for recommended light spectrum ratios."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "light/light_spectrum_guidelines.json"

_DATA: Dict[str, Dict[str, Mapping[str, float]]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_spectrum", "get_red_blue_ratio"]


def list_supported_plants() -> list[str]:
    """Return plant types with light spectrum guidance."""
    return list_dataset_entries(_DATA)


def get_spectrum(plant_type: str, stage: str) -> Dict[str, float]:
    """Return red/blue fractions for a plant stage if available."""
    plant = _DATA.get(normalize_key(plant_type), {})
    info = plant.get(normalize_key(stage))
    result: Dict[str, float] = {}
    if isinstance(info, Mapping):
        for color in ("red", "blue"):
            try:
                value = float(info.get(color))
            except (TypeError, ValueError):
                continue
            result[color] = value
    return result


def get_red_blue_ratio(plant_type: str, stage: str) -> float | None:
    """Return red-to-blue ratio for a plant stage if defined."""
    spec = get_spectrum(plant_type, stage)
    red = spec.get("red")
    blue = spec.get("blue")
    if red is None or blue is None or blue == 0:
        return None
    return round(red / blue, 2)
