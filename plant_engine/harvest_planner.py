"""Utilities for planning growth stage schedules."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

from .growth_stage import list_growth_stages, get_stage_duration

__all__ = ["build_stage_schedule"]


def build_stage_schedule(plant_type: str, start_date: date) -> List[Dict[str, object]]:
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
    stages = list_growth_stages(plant_type)
    schedule: List[Dict[str, object]] = []
    current = start_date
    for stage in stages:
        duration = get_stage_duration(plant_type, stage) or 0
        end = current + timedelta(days=duration)
        schedule.append(
            {
                "stage": stage,
                "start_date": current,
                "end_date": end,
                "duration_days": duration,
            }
        )
        current = end
    return schedule
