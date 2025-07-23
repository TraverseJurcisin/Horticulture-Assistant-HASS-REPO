from __future__ import annotations

"""Utilities for combined pest and disease monitoring schedules."""

from datetime import date
from typing import List

from . import pest_monitor, disease_monitor

__all__ = ["generate_integrated_monitoring_schedule"]


def generate_integrated_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> List[date]:
    """Return merged pest and disease monitoring dates.

    The schedule combines pest and disease intervals, sorted and deduplicated.
    Only the first ``events`` dates are returned.
    """
    if events <= 0:
        return []

    pest = pest_monitor.generate_monitoring_schedule(plant_type, stage, start, events)
    disease = disease_monitor.generate_monitoring_schedule(plant_type, stage, start, events)
    combined = sorted(set(pest + disease))
    return combined[:events]
