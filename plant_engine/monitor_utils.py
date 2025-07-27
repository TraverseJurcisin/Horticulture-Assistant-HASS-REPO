"""Generic helpers for pest and disease monitoring intervals."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Mapping, Dict

from functools import lru_cache

from .utils import normalize_key, load_dataset

__all__ = [
    "get_interval",
    "next_date",
    "generate_schedule",
    "estimate_condition_risk",
    "calculate_risk_score",
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


def estimate_condition_risk(
    factors: Mapping[str, Mapping[str, list]],
    environment: Mapping[str, float],
) -> dict[str, str]:
    """Return risk classification for each condition in ``factors``."""

    from . import environment_manager

    readings = environment_manager.normalize_environment_readings(environment)
    risks: dict[str, str] = {}
    for name, reqs in factors.items():
        matches = 0
        total = 0
        for key, bounds in reqs.items():
            if (
                not isinstance(bounds, (list, tuple))
                or len(bounds) != 2
            ):
                continue
            total += 1
            value = readings.get(key)
            if value is None:
                continue
            low, high = bounds
            if low <= value <= high:
                matches += 1
        if total == 0:
            continue
        if matches == 0:
            level = "low"
        elif matches < total:
            level = "moderate"
        else:
            level = "high"
        risks[normalize_key(name)] = level
    return risks


RISK_SCORE_FILE = "risk_score_map.json"


@lru_cache(maxsize=1)
def _risk_score_map() -> Dict[str, int]:
    """Return mapping of risk levels to numeric scores."""
    raw = load_dataset(RISK_SCORE_FILE)
    scores: Dict[str, int] = {"low": 1, "moderate": 2, "high": 3}
    if isinstance(raw, Mapping):
        for key, val in raw.items():
            try:
                scores[str(key).lower()] = int(val)
            except (TypeError, ValueError):
                continue
    return scores


def calculate_risk_score(risk_map: Mapping[str, str]) -> float:
    """Return average numeric risk score for ``risk_map``."""
    if not risk_map:
        return 0.0
    scores = _risk_score_map()
    total = 0
    count = 0
    for level in risk_map.values():
        total += scores.get(str(level).lower(), 0)
        count += 1
    return round(total / count, 2) if count else 0.0
