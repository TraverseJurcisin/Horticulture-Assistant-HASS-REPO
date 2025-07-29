"""Harvest window utilities."""
from __future__ import annotations

from datetime import date
from typing import Dict, Tuple

from .utils import load_dataset, normalize_key

DATA_FILE = "harvest_windows.json"

_DATA: Dict[str, Tuple[int, int]] = load_dataset(DATA_FILE)

__all__ = [
    "get_harvest_window",
    "is_harvest_time",
]


def get_harvest_window(plant_type: str) -> Tuple[int, int] | None:
    """Return the (start_day, end_day) harvest window for ``plant_type``."""
    window = _DATA.get(normalize_key(plant_type))
    if (
        isinstance(window, (list, tuple))
        and len(window) == 2
        and all(isinstance(v, (int, float)) for v in window)
    ):
        return int(window[0]), int(window[1])
    return None


def is_harvest_time(
    plant_type: str, start_date: date, current_date: date
) -> bool | None:
    """Return ``True`` if ``current_date`` falls within the harvest window."""
    window = get_harvest_window(plant_type)
    if not window:
        return None
    start, end = window
    days_since_start = (current_date - start_date).days
    return start <= days_since_start <= end
