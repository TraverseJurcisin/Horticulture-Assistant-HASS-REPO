"""Utility functions for predicting crop yield from logged harvests."""
from __future__ import annotations

from typing import Dict

from .utils import load_dataset, normalize_key
from .yield_manager import get_total_yield

DATA_FILE = "yield/yield_estimates.json"

# Cached dataset loaded at import time
_YIELD_DATA: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_estimated_yield", "estimate_remaining_yield"]


def list_supported_plants() -> list[str]:
    """Return plant types that have yield estimates available."""
    return sorted(_YIELD_DATA.keys())


def get_estimated_yield(plant_type: str) -> float | None:
    """Return expected total yield (g) for the given plant type."""
    key = normalize_key(plant_type)
    value = _YIELD_DATA.get(key)
    return float(value) if value is not None else None


def estimate_remaining_yield(plant_id: str, plant_type: str) -> float | None:
    """Return remaining yield (g) based on logged harvests.

    Parameters
    ----------
    plant_id : str
        Identifier used with :mod:`plant_engine.yield_manager`.
    plant_type : str
        Crop type used to look up the estimated total yield.
    """
    expected = get_estimated_yield(plant_type)
    if expected is None:
        return None
    harvested = get_total_yield(plant_id)
    remaining = max(0.0, expected - harvested)
    return round(remaining, 2)
