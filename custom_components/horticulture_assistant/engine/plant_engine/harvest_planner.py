"""Utilities for planning growth stage schedules."""

from __future__ import annotations

from datetime import date

from .growth_stage import generate_stage_schedule, predict_harvest_date

__all__ = ["build_stage_schedule", "estimate_harvest_date"]


def build_stage_schedule(plant_type: str, start_date: date) -> list[dict[str, object]]:
    """Return an ordered schedule of growth stages with dates.

    Parameters
    ----------
    plant_type : str
        Crop type defined in ``growth_stages.json``.
    start_date : date
        Planting or germination date.

    Returns
    -------
    List[dict]
        Each dictionary contains ``stage``, ``start_date``, ``end_date`` and
        ``duration_days`` keys. ``end_date`` is exclusive.
    """
    base = generate_stage_schedule(plant_type, start_date)
    schedule: list[dict[str, object]] = []
    for entry in base:
        start = entry["start_date"]
        end = entry["end_date"]
        duration = (end - start).days
        schedule.append({**entry, "duration_days": duration})
    return schedule


def estimate_harvest_date(plant_type: str, start_date: date) -> date | None:
    """Return the predicted harvest date for the crop cycle."""

    return predict_harvest_date(plant_type, start_date)
