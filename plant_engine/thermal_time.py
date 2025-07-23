"""Growing Degree Day (GDD) utilities for growth stage tracking."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset, normalize_key

DATA_FILE = "gdd_requirements.json"

# Cached dataset loaded once
_DATA: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)

__all__ = [
    "calculate_gdd",
    "list_supported_plants",
    "get_stage_gdd_requirement",
    "predict_stage_completion",
    "accumulate_gdd_series",
    "estimate_days_to_stage",
]


def calculate_gdd(temp_min_c: float, temp_max_c: float, base_temp_c: float = 10.0) -> float:
    """Return Growing Degree Days for a single day."""
    if temp_min_c > temp_max_c:
        temp_min_c, temp_max_c = temp_max_c, temp_min_c
    avg = (temp_min_c + temp_max_c) / 2
    gdd = max(0.0, avg - base_temp_c)
    return round(gdd, 1)


def list_supported_plants() -> list[str]:
    """Return plant types with GDD data."""
    return sorted(_DATA.keys())


def get_stage_gdd_requirement(plant_type: str, stage: str) -> int | None:
    """Return cumulative GDD required to reach ``stage`` for ``plant_type``."""
    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return None
    value = plant.get(normalize_key(stage))
    return int(value) if isinstance(value, (int, float)) else None


def predict_stage_completion(plant_type: str, stage: str, accumulated_gdd: float) -> bool:
    """Return ``True`` if ``accumulated_gdd`` meets or exceeds the stage requirement."""
    req = get_stage_gdd_requirement(plant_type, stage)
    if req is None:
        return False
    return accumulated_gdd >= req


def accumulate_gdd_series(temps: Iterable[tuple[float, float]], base_temp_c: float = 10.0) -> float:
    """Return total GDD for a series of (min, max) temperature pairs."""
    total = 0.0
    for t_min, t_max in temps:
        total += calculate_gdd(t_min, t_max, base_temp_c)
    return round(total, 1)


def estimate_days_to_stage(
    plant_type: str,
    stage: str,
    temps: Iterable[tuple[float, float]],
    base_temp_c: float = 10.0,
) -> int | None:
    """Return estimated days needed to reach ``stage`` using ``temps``.

    ``temps`` should be an iterable of (min_c, max_c) pairs ordered by day.
    The function returns ``None`` if the GDD requirement is unknown or the
    provided series is insufficient to reach the target.
    """

    requirement = get_stage_gdd_requirement(plant_type, stage)
    if requirement is None:
        return None

    accumulated = 0.0
    for day, (t_min, t_max) in enumerate(temps, start=1):
        accumulated += calculate_gdd(t_min, t_max, base_temp_c)
        if accumulated >= requirement:
            return day

    return None
