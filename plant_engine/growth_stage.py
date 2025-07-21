"""Retrieve growth stage metadata for plants."""

from __future__ import annotations

from typing import Dict, Any

from .utils import load_dataset

DATA_FILE = "growth_stages.json"



# Load growth stage dataset once. ``load_dataset`` handles caching.
_DATA: Dict[str, Dict[str, Any]] = load_dataset(DATA_FILE)


def _norm(key: str) -> str:
    """Normalize keys for case-insensitive lookups."""
    return key.lower()

__all__ = [
    "get_stage_info",
    "list_growth_stages",
    "get_stage_duration",
    "estimate_stage_from_age",
]


def get_stage_info(plant_type: str, stage: str) -> Dict[str, Any]:
    """Return information about a particular growth stage."""
    return _DATA.get(_norm(plant_type), {}).get(_norm(stage), {})


def list_growth_stages(plant_type: str) -> list[str]:
    """Return all defined growth stages for a plant type."""
    return sorted(_DATA.get(_norm(plant_type), {}).keys())


def get_stage_duration(plant_type: str, stage: str) -> int | None:
    """Return the duration in days for a growth stage if known."""
    info = get_stage_info(plant_type, stage)
    duration = info.get("duration_days")
    if isinstance(duration, (int, float)):
        return int(duration)
    return None


def estimate_stage_from_age(plant_type: str, days_since_start: int) -> str | None:
    """Return the current growth stage given days since planting.

    The ``growth_stages.json`` dataset defines ``duration_days`` for each stage.
    Stages are assumed to occur in the order listed in the dataset.  This helper
    walks through the stages accumulating their durations until the provided age
    falls within a stage's span. ``None`` is returned if the plant type is
    unknown or no match is found.
    """
    if days_since_start < 0:
        raise ValueError("days_since_start must be non-negative")

    stages = _DATA.get(_norm(plant_type))
    if not isinstance(stages, dict):
        return None

    elapsed = 0
    for stage_name, info in stages.items():
        duration = info.get("duration_days")
        if isinstance(duration, (int, float)):
            elapsed += int(duration)
            if days_since_start < elapsed:
                return stage_name

    return None
