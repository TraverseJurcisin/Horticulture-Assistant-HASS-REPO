"""Retrieve growth stage metadata for plants."""

from __future__ import annotations

from typing import Dict, Any, List, Tuple
from datetime import date, timedelta

import pandas as pd

from .utils import load_dataset, normalize_key

DATA_FILE = "growth_stages.json"
GERMINATION_FILE = "germination_duration.json"



# Load growth stage dataset once. ``load_dataset`` handles caching.
_DATA: Dict[str, Dict[str, Any]] = load_dataset(DATA_FILE)
_GERMINATION: Dict[str, int] = load_dataset(GERMINATION_FILE)

# Precompute cumulative stage end days for quick lookups
_STAGE_BOUNDS: Dict[str, List[Tuple[str, int]]] = {}
for plant, stages in _DATA.items():
    if not isinstance(stages, dict):
        continue
    elapsed = 0
    bounds: List[Tuple[str, int]] = []
    for stage, info in stages.items():
        days = info.get("duration_days")
        if isinstance(days, (int, float)):
            elapsed += int(days)
            bounds.append((stage, elapsed))
    if bounds:
        _STAGE_BOUNDS[plant] = bounds



__all__ = [
    "get_stage_info",
    "list_growth_stages",
    "get_stage_duration",
    "estimate_stage_from_age",
    "estimate_stage_from_date",
    "predict_harvest_date",
    "get_total_cycle_duration",
    "stage_progress",
    "cycle_progress",
    "days_until_harvest",
    "predict_next_stage_date",
    "predict_stage_end_date",
    "stage_progress_from_dates",
    "cycle_progress_from_dates",
    "get_germination_duration",
    "growth_stage_summary",
    "stage_bounds",
    "generate_stage_schedule",
    "stage_schedule_df",
]


def get_stage_info(plant_type: str, stage: str) -> Dict[str, Any]:
    """Return information about a particular growth stage."""
    return _DATA.get(normalize_key(plant_type), {}).get(normalize_key(stage), {})


def list_growth_stages(plant_type: str) -> list[str]:
    """Return all defined growth stages for a plant type."""
    stages = _DATA.get(normalize_key(plant_type), {})
    return list(stages.keys())


def get_stage_duration(plant_type: str, stage: str) -> int | None:
    """Return the duration in days for a growth stage if known."""
    info = get_stage_info(plant_type, stage)
    duration = info.get("duration_days")
    if isinstance(duration, (int, float)):
        return int(duration)
    return None


def get_total_cycle_duration(plant_type: str) -> int | None:
    """Return total days for all stages of ``plant_type`` if available."""

    stages = _DATA.get(normalize_key(plant_type))
    if not isinstance(stages, dict):
        return None
    total = 0
    for info in stages.values():
        days = info.get("duration_days")
        if isinstance(days, (int, float)):
            total += int(days)
    return total if total > 0 else None


def stage_bounds(plant_type: str) -> List[Tuple[str, int]]:
    """Return cumulative ``(stage, end_day)`` pairs for ``plant_type``."""

    return list(_STAGE_BOUNDS.get(normalize_key(plant_type), []))


def estimate_stage_from_age(plant_type: str, days_since_start: int) -> str | None:
    """Return the current growth stage given days since planting."""

    if days_since_start < 0:
        raise ValueError("days_since_start must be non-negative")

    bounds = stage_bounds(plant_type)
    for stage_name, end_day in bounds:
        if days_since_start < end_day:
            return stage_name

    return None


def estimate_stage_from_date(
    plant_type: str, start_date: date, current_date: date
) -> str | None:
    """Return growth stage for ``current_date`` based on ``start_date``."""

    days = (current_date - start_date).days
    if days < 0:
        raise ValueError("current_date cannot be before start_date")
    return estimate_stage_from_age(plant_type, days)


def predict_harvest_date(plant_type: str, start_date: date) -> date | None:
    """Return estimated harvest date based on growth stage durations."""
    stages = _DATA.get(normalize_key(plant_type))
    if not isinstance(stages, dict):
        return None

    total_days = 0
    for info in stages.values():
        days = info.get("duration_days")
        if isinstance(days, (int, float)):
            total_days += int(days)

    return start_date + timedelta(days=total_days)


def stage_progress(plant_type: str, stage: str, days_elapsed: int) -> float | None:
    """Return percentage completion of ``stage`` based on ``days_elapsed``.

    The returned value is clipped to the range 0-100. ``None`` is returned when
    the stage duration is unknown.
    """

    duration = get_stage_duration(plant_type, stage)
    if duration is None:
        return None
    if days_elapsed < 0:
        raise ValueError("days_elapsed must be non-negative")
    progress = min(max(days_elapsed / duration, 0.0), 1.0)
    return round(progress * 100, 1)


def cycle_progress(plant_type: str, days_since_start: int) -> float | None:
    """Return percent completion of the entire growth cycle."""

    total = get_total_cycle_duration(plant_type)
    if total is None:
        return None
    if days_since_start < 0:
        raise ValueError("days_since_start must be non-negative")
    progress = min(max(days_since_start / total, 0.0), 1.0)
    return round(progress * 100, 1)


def days_until_harvest(
    plant_type: str, start_date: date, current_date: date
) -> int | None:
    """Return the number of days until the estimated harvest date."""

    harvest = predict_harvest_date(plant_type, start_date)
    if harvest is None:
        return None
    remaining = (harvest - current_date).days
    return max(0, remaining)


def predict_next_stage_date(
    plant_type: str, current_stage: str, stage_start: date
) -> date | None:
    """Return the estimated start date of the stage following ``current_stage``.

    Parameters
    ----------
    plant_type : str
        Plant type used to look up stage durations.
    current_stage : str
        Name of the current stage in the growth cycle.
    stage_start : date
        Date when ``current_stage`` began.

    Returns
    -------
    date | None
        The expected date of the next stage transition or ``None`` if unknown.
    """

    duration = get_stage_duration(plant_type, current_stage)
    if duration is None:
        return None
    return stage_start + timedelta(days=duration)


def predict_stage_end_date(
    plant_type: str, stage: str, stage_start: date
) -> date | None:
    """Return the expected end date of ``stage`` for ``plant_type``."""

    duration = get_stage_duration(plant_type, stage)
    if duration is None:
        return None
    return stage_start + timedelta(days=duration)


def stage_progress_from_dates(
    plant_type: str,
    stage: str,
    start_date: date,
    current_date: date,
) -> float | None:
    """Return completion percent of ``stage`` based on dates."""

    if current_date < start_date:
        raise ValueError("current_date cannot be before start_date")
    days = (current_date - start_date).days
    return stage_progress(plant_type, stage, days)


def cycle_progress_from_dates(
    plant_type: str, start_date: date, current_date: date
) -> float | None:
    """Return completion percent of the entire growth cycle based on dates."""

    if current_date < start_date:
        raise ValueError("current_date cannot be before start_date")
    days = (current_date - start_date).days
    return cycle_progress(plant_type, days)


def days_until_next_stage(
    plant_type: str, current_stage: str, days_elapsed: int
) -> int | None:
    """Return days remaining in ``current_stage`` for ``plant_type``.

    Parameters
    ----------
    plant_type : str
        Crop identifier for growth stage lookup.
    current_stage : str
        Name of the current stage.
    days_elapsed : int
        Days spent in the current stage so far.

    Returns
    -------
    int | None
        Number of days until the next stage begins or ``None`` if the
        duration is unknown.
    """

    if days_elapsed < 0:
        raise ValueError("days_elapsed must be non-negative")

    duration = get_stage_duration(plant_type, current_stage)
    if duration is None:
        return None
    remaining = duration - days_elapsed
    return max(0, remaining)


def get_germination_duration(plant_type: str) -> int | None:
    """Return default days to germination for ``plant_type`` if known."""

    value = _GERMINATION.get(normalize_key(plant_type))
    if isinstance(value, (int, float)):
        return int(value)
    return None


def growth_stage_summary(
    plant_type: str,
    start_date: date | None = None,
    *,
    include_guidelines: bool = False,
) -> Dict[str, Any]:
    """Return growth stage durations with optional guideline data.

    When ``include_guidelines`` is ``True`` each stage entry also contains
    recommended environment and nutrient targets pulled from the respective
    datasets. This avoids repetitive lookups when generating reports.
    """

    stages = list_growth_stages(plant_type)
    summary = []
    for stage in stages:
        entry = {
            "stage": stage,
            "duration_days": get_stage_duration(plant_type, stage),
        }
        if include_guidelines:
            from .environment_manager import get_environment_guidelines
            from .nutrient_manager import get_recommended_levels

            entry["environment"] = get_environment_guidelines(
                plant_type, stage
            ).as_dict()
            entry["nutrients"] = get_recommended_levels(plant_type, stage)
        summary.append(entry)

    result = {"plant_type": plant_type, "stages": summary}

    total = get_total_cycle_duration(plant_type)
    if total is not None:
        result["total_cycle_days"] = total

    germ = get_germination_duration(plant_type)
    if germ is not None:
        result["germination_days"] = germ

    if start_date and total is not None:
        result["predicted_harvest_date"] = start_date + timedelta(days=total)
    elif start_date:
        harvest = predict_harvest_date(plant_type, start_date)
        if harvest:
            result["predicted_harvest_date"] = harvest

    return result


def generate_stage_schedule(plant_type: str, start_date: date) -> list[dict[str, date]]:
    """Return ordered stage schedule with start and end dates."""

    stages = list_growth_stages(plant_type)
    if not stages:
        return []

    schedule: list[dict[str, date]] = []
    current = start_date
    for stage in stages:
        duration = get_stage_duration(plant_type, stage)
        if duration is None:
            break
        end_date = current + timedelta(days=duration)
        schedule.append({"stage": stage, "start_date": current, "end_date": end_date})
        current = end_date

    return schedule


def stage_schedule_df(plant_type: str, start_date: date) -> "pd.DataFrame":
    """Return stage schedule as a :class:`pandas.DataFrame`."""

    schedule = generate_stage_schedule(plant_type, start_date)
    if not schedule:
        return pd.DataFrame()
    df = pd.DataFrame(schedule)
    df["start_date"] = pd.to_datetime(df["start_date"])  # type: ignore[arg-type]
    df["end_date"] = pd.to_datetime(df["end_date"])  # type: ignore[arg-type]
    return df
