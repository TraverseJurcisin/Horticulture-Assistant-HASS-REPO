"""Phenological milestone prediction utilities."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable

from . import thermal_time
from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "phenological_milestones.json"

_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_milestone_info",
    "get_milestone_gdd_requirement",
    "get_milestone_photoperiod_requirement",
    "predict_milestone",
    "estimate_days_to_milestone",
    "estimate_milestone_date",
    "format_milestone_prediction",
]


def list_supported_plants() -> list[str]:
    """Return plant types with phenological milestone data."""
    return list_dataset_entries(_DATA)


def get_milestone_info(plant_type: str, milestone: str) -> dict:
    """Return info for ``milestone`` of ``plant_type``."""
    return _DATA.get(normalize_key(plant_type), {}).get(normalize_key(milestone), {})


def get_milestone_gdd_requirement(plant_type: str, milestone: str) -> float | None:
    """Return GDD requirement for reaching ``milestone``."""
    info = get_milestone_info(plant_type, milestone)
    value = info.get("gdd")
    return float(value) if isinstance(value, (int, float)) else None


def get_milestone_photoperiod_requirement(
    plant_type: str, milestone: str
) -> float | None:
    """Return day length requirement for ``milestone`` if available."""
    info = get_milestone_info(plant_type, milestone)
    value = info.get("photoperiod_hours")
    return float(value) if isinstance(value, (int, float)) else None


def predict_milestone(plant_type: str, milestone: str, accumulated_gdd: float) -> bool:
    """Return ``True`` if ``accumulated_gdd`` meets the milestone requirement."""
    req = get_milestone_gdd_requirement(plant_type, milestone)
    if req is None:
        return False
    return accumulated_gdd >= req


def estimate_days_to_milestone(
    plant_type: str,
    milestone: str,
    temps: Iterable[tuple[float, float]],
    base_temp_c: float = 10.0,
) -> int | None:
    """Return estimated days needed to reach ``milestone`` using ``temps``."""
    requirement = get_milestone_gdd_requirement(plant_type, milestone)
    if requirement is None:
        return None

    accumulated = 0.0
    for day, (t_min, t_max) in enumerate(temps, start=1):
        accumulated += thermal_time.calculate_gdd(t_min, t_max, base_temp_c)
        if accumulated >= requirement:
            return day

    return None


def estimate_milestone_date(
    plant_type: str,
    milestone: str,
    start_date: date,
    temps: Iterable[tuple[float, float]],
    base_temp_c: float = 10.0,
) -> date | None:
    """Return predicted date when ``milestone`` will be reached."""
    days = estimate_days_to_milestone(plant_type, milestone, temps, base_temp_c)
    if days is None:
        return None
    return start_date + timedelta(days=days)


def format_milestone_prediction(
    plant_name: str,
    plant_type: str,
    milestone: str,
    accumulated_gdd: float,
    temps: Iterable[tuple[float, float]],
    base_temp_c: float = 10.0,
) -> str:
    """Return human-friendly milestone prediction message.

    The message references ``plant_name`` and includes the expected
    days to reach ``milestone`` based on the provided temperature
    forecast ``temps``. A small ±2 day window is given to account
    for uncertainty in the forecast.
    """

    days = estimate_days_to_milestone(
        plant_type, milestone, temps, base_temp_c
    )
    if days is None:
        return (
            f"{plant_name} has reached {accumulated_gdd:.0f} GDD since last reset."
        )

    low = max(0, days - 2)
    high = days + 2
    return (
        f"{plant_name} has reached {accumulated_gdd:.0f} GDD since last reset. "
        f"Expect {milestone.replace('_', ' ')} within {low}–{high} days."
    )

