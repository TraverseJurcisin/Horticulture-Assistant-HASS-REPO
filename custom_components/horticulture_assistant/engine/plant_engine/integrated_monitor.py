from __future__ import annotations

"""Utilities for combined pest and disease monitoring schedules."""

from datetime import date
from typing import List, Mapping, Dict, Any

from . import pest_monitor, disease_monitor

__all__ = [
    "generate_integrated_monitoring_schedule",
    "summarize_integrated_management",
]


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


def summarize_integrated_management(
    plant_type: str,
    stage: str | None,
    pests: Mapping[str, int],
    diseases: Mapping[str, int],
    environment: Mapping[str, float] | None = None,
    last_date: date | None = None,
) -> Dict[str, Any]:
    """Return combined pest and disease management summary."""

    pest_summary = pest_monitor.summarize_pest_management(
        plant_type,
        stage,
        pests,
        environment=environment,
        last_date=last_date,
    )
    disease_summary = disease_monitor.summarize_disease_management(
        plant_type,
        stage,
        diseases,
        environment=environment,
        last_date=last_date,
    )

    return {"pests": pest_summary, "diseases": disease_summary}
