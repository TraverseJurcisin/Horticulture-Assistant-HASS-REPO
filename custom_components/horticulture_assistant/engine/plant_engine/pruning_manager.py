"""Pruning guideline helpers."""

from __future__ import annotations

from datetime import date, timedelta

from .utils import (list_dataset_entries, load_dataset, normalize_key,
                    stage_value)

DATA_FILE = "pruning/pruning_guidelines.json"
INTERVAL_FILE = "pruning/pruning_intervals.json"

# Loaded once via load_dataset which uses caching
_DATA: dict[str, dict[str, str]] = load_dataset(DATA_FILE)
_INTERVALS: dict[str, dict[str, int]] = load_dataset(INTERVAL_FILE)

__all__ = [
    "list_supported_plants",
    "list_stages",
    "get_pruning_instructions",
    "get_pruning_interval",
    "next_pruning_date",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with pruning data."""
    return list_dataset_entries(_DATA)


def list_stages(plant_type: str) -> list[str]:
    """Return available pruning stages for ``plant_type``."""
    return sorted(_DATA.get(normalize_key(plant_type), {}).keys())


def get_pruning_instructions(plant_type: str, stage: str) -> str:
    """Return pruning instructions for a plant type and stage."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return ""
    return plant.get(normalize_key(stage), "")


def get_pruning_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between pruning events."""

    value = stage_value(_INTERVALS, plant_type, stage)
    if isinstance(value, int | float):
        return int(value)
    return None


def next_pruning_date(plant_type: str, stage: str | None, last_date: date) -> date | None:
    """Return the next pruning date for a plant stage."""

    interval = get_pruning_interval(plant_type, stage)
    if interval is None:
        return None
    return last_date + timedelta(days=interval)
