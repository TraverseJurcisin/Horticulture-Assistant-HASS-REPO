"""Access nutrient absorption rate data and helpers."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache

from .utils import (
    clean_float_map,
    list_dataset_entries,
    load_dataset,
    normalize_key,
)

DATA_FILE = "nutrients/nutrient_absorption_rates.json"


@lru_cache(maxsize=1)
def _rates() -> dict[str, dict[str, float]]:
    """Return cached absorption rates mapped by normalized stage."""
    raw = load_dataset(DATA_FILE)
    rates: dict[str, dict[str, float]] = {}
    for stage, data in raw.items():
        if not isinstance(data, Mapping):
            continue
        stage_key = normalize_key(stage)
        stage_rates = clean_float_map(data)
        if stage_rates:
            rates[stage_key] = stage_rates
    return rates


def list_stages() -> list[str]:
    """Return stages with absorption rate definitions."""
    return list_dataset_entries(_rates())


def get_absorption_rates(stage: str) -> dict[str, float]:
    """Return nutrient absorption rates for ``stage``."""
    return _rates().get(normalize_key(stage), {})


def apply_absorption_rates(schedule: Mapping[str, float], stage: str) -> dict[str, float]:
    """Return ``schedule`` adjusted for nutrient absorption efficiency."""
    rates = get_absorption_rates(stage)
    if not rates:
        return dict(schedule)
    adjusted: dict[str, float] = {}
    for nutrient, grams in schedule.items():
        rate = rates.get(nutrient)
        try:
            grams_f = float(grams)
        except (TypeError, ValueError):
            continue
        if rate and rate > 0:
            grams_f /= rate
        adjusted[nutrient] = round(grams_f, 2)
    return adjusted


__all__ = [
    "list_stages",
    "get_absorption_rates",
    "apply_absorption_rates",
]
