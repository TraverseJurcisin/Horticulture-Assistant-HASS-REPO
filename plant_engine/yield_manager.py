"""Functions for tracking harvest yield data."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List

from .utils import load_json, save_json

# Default yield directory. Can be overridden with the ``HORTICULTURE_YIELD_DIR``
# environment variable to support custom data locations during testing or
# deployment.
YIELD_DIR = os.getenv("HORTICULTURE_YIELD_DIR", "data/yield")


@dataclass
class HarvestRecord:
    """Single harvest entry."""

    date: str
    yield_grams: float
    fruit_count: int | None = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _yield_path(plant_id: str) -> str:
    """Return file path for the plant yield history."""
    return os.path.join(YIELD_DIR, f"{plant_id}.json")


def _load_raw_history(plant_id: str) -> Dict[str, List[Dict[str, object]]]:
    """Return raw history mapping from disk."""
    if os.path.exists(_yield_path(plant_id)):
        return load_json(_yield_path(plant_id))
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


__all__ = [
    "HarvestRecord",
    "load_yield_history",
    "record_harvest",
    "get_total_yield",
]
