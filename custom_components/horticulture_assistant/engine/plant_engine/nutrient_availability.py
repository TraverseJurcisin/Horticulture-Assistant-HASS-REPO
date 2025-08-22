"""Nutrient availability estimation based on solution pH."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable, Tuple

from .utils import load_dataset, list_dataset_entries

DATA_FILE = "nutrients/nutrient_availability_ph.json"

_DATA: Dict[str, Iterable[float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_nutrients",
    "get_optimal_ph",
    "availability_factor",
    "availability_for_all",
]

Range = Tuple[float, float]


@lru_cache(maxsize=None)
def list_supported_nutrients() -> list[str]:
    """Return nutrient codes with availability data."""
    return list_dataset_entries(_DATA)


@lru_cache(maxsize=None)
def get_optimal_ph(nutrient: str) -> Range | None:
    """Return optimal pH range for ``nutrient`` if known."""
    rng = _DATA.get(nutrient)
    if isinstance(rng, Iterable):
        vals = list(rng)
        if len(vals) == 2:
            try:
                return float(vals[0]), float(vals[1])
            except (TypeError, ValueError):
                return None
    return None


def availability_factor(nutrient: str, ph: float) -> float:
    """Return relative availability of ``nutrient`` at ``ph`` between 0 and 1."""
    if ph <= 0:
        raise ValueError("pH must be positive")
    rng = get_optimal_ph(nutrient)
    if not rng:
        return 1.0
    low, high = rng
    if low <= ph <= high:
        return 1.0
    dist = low - ph if ph < low else ph - high
    factor = max(0.0, 1 - dist / 3)
    return round(factor, 2)


def availability_for_all(ph: float) -> Dict[str, float]:
    """Return availability factors for all known nutrients at ``ph``."""
    return {n: availability_factor(n, ph) for n in list_supported_nutrients()}
