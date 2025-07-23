"""CO₂ cost calculations and source metadata."""
from __future__ import annotations

from typing import Dict, List

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "co2_prices.json"

# Load once using caching in :func:`load_dataset`
_DATA: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["list_sources", "get_co2_price", "estimate_injection_cost"]


def list_sources() -> List[str]:
    """Return available CO₂ source identifiers."""
    return list_dataset_entries(_DATA)


def get_co2_price(source: str) -> float | None:
    """Return price per kg of CO₂ for ``source`` if known."""
    val = _DATA.get(normalize_key(source))
    if isinstance(val, (int, float)):
        return float(val)
    return None


def estimate_injection_cost(grams: float, source: str = "compressed") -> float:
    """Return estimated cost in USD for ``grams`` of CO₂."""
    if grams < 0:
        raise ValueError("grams must be non-negative")
    price = get_co2_price(source)
    if price is None:
        raise KeyError(f"Price for '{source}' is not defined")
    kg = grams / 1000
    return round(price * kg, 2)
