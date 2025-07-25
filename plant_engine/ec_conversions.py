"""Utilities for converting electrical conductivity (EC) to nutrient ppm and vice versa."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "ec_to_ppm_factors.json"

_FACTORS: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = [
    "list_scales",
    "get_factor",
    "ec_to_ppm",
    "ppm_to_ec",
]

@lru_cache(maxsize=None)
def list_scales() -> list[str]:
    """Return available conversion scale names."""
    return list_dataset_entries(_FACTORS)

@lru_cache(maxsize=None)
def get_factor(scale: str) -> float | None:
    """Return the ppm conversion factor for ``scale`` or ``None`` if unknown."""
    key = normalize_key(scale)
    value = _FACTORS.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def ec_to_ppm(ec: float, scale: str | float = "500") -> float:
    """Return approximate ppm for ``ec`` (mS/cm) using ``scale``."""
    if isinstance(scale, (int, float)):
        factor = float(scale)
    else:
        factor = get_factor(scale) or 500.0
    return round(ec * factor, 2)

def ppm_to_ec(ppm: float, scale: str | float = "500") -> float:
    """Return EC (mS/cm) from ``ppm`` using ``scale``."""
    if isinstance(scale, (int, float)):
        factor = float(scale)
    else:
        factor = get_factor(scale) or 500.0
    if factor == 0:
        raise ValueError("conversion factor must be non-zero")
    return round(ppm / factor, 3)
