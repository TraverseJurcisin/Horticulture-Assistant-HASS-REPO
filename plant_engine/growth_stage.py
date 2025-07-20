"""Retrieve growth stage metadata for plants."""

from __future__ import annotations

from typing import Dict, Any
from functools import lru_cache
from .utils import load_dataset

DATA_FILE = "growth_stages.json"


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Dict[str, Any]]:
    return load_dataset(DATA_FILE)


def get_stage_info(plant_type: str, stage: str) -> Dict[str, Any]:
    """Return information about a particular growth stage."""
    return _load_data().get(plant_type, {}).get(stage, {})


def list_growth_stages(plant_type: str) -> list[str]:
    """Return all defined growth stages for a plant type."""
    return sorted(_load_data().get(plant_type, {}).keys())


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

    stages = _load_data().get(plant_type)
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
