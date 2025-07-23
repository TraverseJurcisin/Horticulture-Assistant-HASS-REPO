"""Generic helpers for pest and disease monitoring intervals."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Mapping

from .utils import normalize_key

__all__ = [
    "get_interval",
    "next_date",
    "generate_schedule",
]


def get_interval(
    data: Mapping[str, Mapping[str, int]],
    plant_type: str,
    stage: str | None = None,
) -> int | None:
    """Return monitoring interval in days for a plant stage."""
    plant = data.get(normalize_key(plant_type), {})
    if stage:
        value = plant.get(normalize_key(stage))
        if isinstance(value, (int, float)):
            return int(value)
    value = plant.get("optimal")
    return int(value) if isinstance(value, (int, float)) else None


def next_date(
    data: Mapping[str, Mapping[str, int]],
    plant_type: str,
    stage: str | None,
    last_date: date,
) -> date | None:
    """Return the next monitoring date based on ``last_date``."""
    interval = get_interval(data, plant_type, stage)
    if interval is None:
        return None
    return last_date + timedelta(days=interval)


def generate_schedule(
    data: Mapping[str, Mapping[str, int]],
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[date]:
    """Return list of future monitoring dates."""
    interval = get_interval(data, plant_type, stage)
    if interval is None or events <= 0:
        return []
    return [start + timedelta(days=interval * i) for i in range(1, events + 1)]
