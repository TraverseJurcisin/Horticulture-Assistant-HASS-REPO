"""Water cost utilities."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "water_costs.json"

_DATA: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["get_water_cost_rate", "estimate_water_cost"]


@lru_cache(maxsize=None)
def get_water_cost_rate(region: str | None = None) -> float:
    """Return cost per liter for ``region`` or the default rate."""
    key = normalize_key(region) if region else "default"
    rate = _DATA.get(key, _DATA.get("default", 0.0))
    try:
        return float(rate)
    except (TypeError, ValueError):
        return 0.0


def estimate_water_cost(volume_l: float, region: str | None = None) -> float:
    """Return cost for ``volume_l`` liters of water in ``region``."""
    if volume_l < 0:
        raise ValueError("volume_l must be non-negative")
    rate = get_water_cost_rate(region)
    return round(volume_l * rate, 4)
