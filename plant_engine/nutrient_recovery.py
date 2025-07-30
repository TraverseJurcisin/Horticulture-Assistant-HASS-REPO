"""Helpers for nutrient recovery factors.

This module loads fractional nutrient recovery values
that represent the portion of applied nutrient expected to
be taken up by plants. Recovery factors can vary by crop
and nutrient. The dataset ``nutrient_recovery_factors.json``
contains defaults and optional per-crop overrides.
"""

from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset

DATA_FILE = "nutrients/nutrient_recovery_factors.json"

# Load dataset once using the cached loader
_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_recovery_factor",
    "get_recovery_factors",
    "estimate_recovered_amounts",
    "adjust_for_recovery",
]


def list_known_nutrients() -> list[str]:
    """Return nutrients with defined recovery factors."""
    defaults = _DATA.get("default", {})
    others = [n for plant in _DATA.values() if isinstance(plant, Mapping) for n in plant]
    return sorted(set(defaults) | set(others))


def get_recovery_factor(nutrient: str, plant_type: str | None = None) -> float:
    """Return fractional recovery factor for ``nutrient``.

    Crop specific overrides are used when available, otherwise the
    ``default`` value from the dataset is returned. Missing values
    default to ``0``.
    """
    if plant_type:
        plant = _DATA.get(plant_type.lower())
        if isinstance(plant, Mapping):
            rate = plant.get(nutrient)
            if rate is not None:
                try:
                    return float(rate)
                except (TypeError, ValueError):
                    return 0.0
    try:
        return float(_DATA.get("default", {}).get(nutrient, 0.0))
    except (TypeError, ValueError):
        return 0.0


def get_recovery_factors(plant_type: str | None = None) -> Dict[str, float]:
    """Return mapping of recovery factors for ``plant_type``.

    When ``plant_type`` is ``None`` or no crop-specific data exists, the
    default factors are returned. Crop overrides supplement the defaults so
    missing values fall back to the generic definitions.
    """

    defaults = _DATA.get("default", {})
    factors: Dict[str, float] = {}

    if plant_type:
        crop = _DATA.get(plant_type.lower())
        if isinstance(crop, Mapping):
            for nutrient, value in crop.items():
                try:
                    factors[nutrient] = float(value)
                except (TypeError, ValueError):
                    continue

    for nutrient, value in defaults.items():
        if nutrient not in factors:
            try:
                factors[nutrient] = float(value)
            except (TypeError, ValueError):
                continue

    return factors


def estimate_recovered_amounts(levels_mg: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return recovered nutrient amounts (mg) given applied levels."""
    recovered: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        factor = get_recovery_factor(nutrient, plant_type)
        if factor <= 0:
            continue
        recovered[nutrient] = round(float(mg) * factor, 2)
    return recovered


def adjust_for_recovery(levels_mg: Mapping[str, float], plant_type: str | None = None) -> Dict[str, float]:
    """Return adjusted nutrient amounts accounting for recovery factors."""
    recovered = estimate_recovered_amounts(levels_mg, plant_type)
    adjusted: Dict[str, float] = {}
    for nutrient, mg in levels_mg.items():
        adj = mg - recovered.get(nutrient, 0.0)
        adjusted[nutrient] = round(adj, 2)
    return adjusted
