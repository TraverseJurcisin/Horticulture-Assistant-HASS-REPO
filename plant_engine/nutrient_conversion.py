"""Helpers for converting oxide nutrient measurements to elemental values."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "nutrient_conversion_factors.json"

__all__ = ["get_conversion_factors", "oxide_to_elemental"]


@lru_cache(maxsize=None)
def get_conversion_factors() -> Dict[str, float]:
    """Return mapping of oxide formulas to fractional elemental factors."""
    data = load_dataset(DATA_FILE)
    factors: Dict[str, float] = {}
    for k, v in data.items():
        key = normalize_key(k).upper()
        try:
            factors[key] = float(v)
        except (TypeError, ValueError):
            continue
    return factors


def oxide_to_elemental(oxide: str, grams: float) -> float:
    """Return grams of elemental nutrient contained in ``grams`` of ``oxide``."""
    if grams < 0:
        raise ValueError("grams must be non-negative")
    factors = get_conversion_factors()
    key = normalize_key(oxide).upper()
    factor = factors.get(key)
    if factor is None:
        raise KeyError(f"Unknown oxide '{oxide}'")
    return round(grams * factor, 3)
