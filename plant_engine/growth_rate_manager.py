"""Simple growth rate utilities using the growth_rate_guidelines dataset."""

from __future__ import annotations

from typing import Dict

from .utils import load_dataset, list_dataset_entries, normalize_key

DATA_FILE = "stages/growth_rate_guidelines.json"

# Load dataset once at import time using cached helper
_DATA: Dict[str, Dict[str, float]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_daily_growth_rate",
    "estimate_growth",
]


def list_supported_plants() -> list[str]:
    """Return plant types with growth rate data available."""
    return list_dataset_entries(_DATA)


def get_daily_growth_rate(plant_type: str, stage: str) -> float | None:
    """Return grams per day growth rate for ``plant_type`` at ``stage``."""
    value = _DATA.get(normalize_key(plant_type), {}).get(normalize_key(stage))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def estimate_growth(plant_type: str, stage: str, days: float) -> float:
    """Return estimated grams gained over ``days`` at the stage growth rate."""
    if days < 0:
        raise ValueError("days must be non-negative")
    rate = get_daily_growth_rate(plant_type, stage)
    if rate is None:
        return 0.0
    return round(rate * days, 2)
