"""Utility helpers for fertilizer dilution limits."""
from __future__ import annotations

from functools import lru_cache
from typing import Mapping, Dict

from .utils import load_dataset, normalize_key

DATA_FILE = "fertilizers/fertilizer_dilution_limits.json"


@lru_cache(maxsize=None)
def _DATA() -> Dict[str, float]:
    """Return normalized dilution limit mapping."""
    raw = load_dataset(DATA_FILE) or {}
    limits: Dict[str, float] = {}
    for key, value in raw.items():
        try:
            limits[normalize_key(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return limits


def get_limit(fertilizer_id: str) -> float | None:
    """Return grams per liter limit for ``fertilizer_id`` if defined."""
    return _DATA().get(normalize_key(fertilizer_id))


def check_schedule(schedule: Mapping[str, float], volume_l: float) -> Dict[str, float]:
    """Return overage grams per liter for items exceeding limits."""
    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    warnings: Dict[str, float] = {}
    for fert_id, grams in schedule.items():
        if grams <= 0:
            continue
        limit = get_limit(fert_id)
        if limit is None:
            continue
        over = grams / volume_l - limit
        if over > 0:
            warnings[fert_id] = round(over, 2)
    return warnings


__all__ = ["get_limit", "check_schedule"]
