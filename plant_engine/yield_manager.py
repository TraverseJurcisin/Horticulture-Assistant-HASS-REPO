"""Functions for tracking harvest yield data."""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List

from . import nutrient_budget

from .utils import load_json, save_json, load_dataset, normalize_key

# Default yield directory. Can be overridden with the ``HORTICULTURE_YIELD_DIR``
# environment variable to support custom data locations during testing or
# deployment.
YIELD_DIR = os.getenv("HORTICULTURE_YIELD_DIR", "data/yield")

# Expected total yields per crop (grams)
YIELD_ESTIMATE_FILE = "yield/yield_estimates.json"

# Cached dataset so repeated lookups avoid disk I/O
_YIELD_ESTIMATES: Dict[str, float] = load_dataset(YIELD_ESTIMATE_FILE)


@dataclass(slots=True)
class HarvestRecord:
    """Single harvest entry."""

    date: str
    yield_grams: float
    fruit_count: int | None = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _yield_path(plant_id: str) -> Path:
    """Return file path for the plant yield history."""
    return Path(YIELD_DIR) / f"{plant_id}.json"


def _load_raw_history(plant_id: str) -> Dict[str, List[Dict[str, object]]]:
    """Return raw history mapping from disk."""
    path = _yield_path(plant_id)
    if path.exists():
        return load_json(path)
    return {"harvests": []}


def load_yield_history(plant_id: str) -> List[HarvestRecord]:
    """Return a list of harvest records for the plant."""
    data = _load_raw_history(plant_id)
    return [HarvestRecord(**entry) for entry in data.get("harvests", [])]


def record_harvest(
    plant_id: str,
    *,
    grams: float,
    fruit_count: int | None = None,
    date: str | None = None,
) -> None:
    """Record a harvest entry for the given plant."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    history = load_yield_history(plant_id)
    history.append(HarvestRecord(date=date, yield_grams=grams, fruit_count=fruit_count))
    save_json(
        _yield_path(plant_id),
        {"harvests": [rec.to_dict() for rec in history]},
    )


def get_total_yield(plant_id: str) -> float:
    """Return total yield in grams for the plant."""
    history = load_yield_history(plant_id)
    return sum(record.yield_grams for record in history)


def get_average_yield(plant_id: str) -> float:
    """Return average yield per harvest for the plant."""
    history = load_yield_history(plant_id)
    if not history:
        return 0.0
    total = sum(record.yield_grams for record in history)
    return round(total / len(history), 2)


def get_total_nutrient_removal(plant_id: str, plant_type: str) -> nutrient_budget.RemovalEstimate:
    """Return cumulative nutrient removal for ``plant_id``.

    The function sums all recorded harvest weights and multiplies by the
    per-kilogram removal rates defined in :data:`nutrient_removal_rates.json`.
    """

    total_yield_kg = get_total_yield(plant_id) / 1000
    return nutrient_budget.estimate_total_removal(plant_type, total_yield_kg)


def get_yield_estimate(plant_type: str) -> float | None:
    """Return expected total yield for ``plant_type`` in grams if known."""

    key = normalize_key(plant_type)
    value = _YIELD_ESTIMATES.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def estimate_yield_performance(plant_id: str, plant_type: str) -> float | None:
    """Return harvested yield fraction compared to the expected yield."""

    estimate = get_yield_estimate(plant_type)
    if estimate is None or estimate <= 0:
        return None
    total = get_total_yield(plant_id)
    return round(total / estimate, 2)


__all__ = [
    "HarvestRecord",
    "load_yield_history",
    "record_harvest",
    "get_total_yield",
    "get_average_yield",
    "get_total_nutrient_removal",
    "get_yield_estimate",
    "estimate_yield_performance",
]
