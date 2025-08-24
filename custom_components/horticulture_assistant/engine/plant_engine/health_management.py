from __future__ import annotations

"""Utilities for integrated pest and disease management."""

from collections.abc import Iterable, Mapping
from typing import Any

from . import (
    disease_manager,
    disease_monitor,
    pest_manager,
    pest_monitor,
)

__all__ = ["generate_management_plan"]


def generate_management_plan(
    plant_type: str,
    pests: Iterable[str] | None = None,
    diseases: Iterable[str] | None = None,
    *,
    pest_severity: Mapping[str, str] | None = None,
    disease_severity: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return consolidated management actions for pests and diseases.

    Parameters
    ----------
    plant_type:
        Crop identifier used for guideline lookups.
    pests:
        Iterable of observed pest names.
    diseases:
        Iterable of observed disease names.
    pest_severity:
        Optional mapping of pest names to severity levels.
    disease_severity:
        Optional mapping of disease names to severity levels.

    Returns
    -------
    Dict[str, Any]
        Mapping with ``"pest_management"`` and ``"disease_management"`` entries.
    """

    pests = list(pests or [])
    diseases = list(diseases or [])

    pest_plan = pest_manager.build_pest_management_plan(plant_type, pests)
    if pest_severity:
        for pest, level in pest_severity.items():
            action = pest_monitor.get_severity_action(level)
            if action:
                pest_plan.setdefault(pest, {})["severity_action"] = action

    disease_actions = disease_manager.recommend_treatments(plant_type, diseases)
    disease_prev = disease_manager.recommend_prevention(plant_type, diseases)
    disease_plan: dict[str, dict[str, Any]] = {}
    for disease in diseases:
        disease_plan[disease] = {
            "treatment": disease_actions.get(disease, "No guideline available"),
            "prevention": disease_prev.get(disease, "No guideline available"),
        }
    if disease_severity:
        for dis, level in disease_severity.items():
            action = disease_monitor.get_severity_action(level)
            if action:
                disease_plan.setdefault(dis, {})["severity_action"] = action

    return {"pest_management": pest_plan, "disease_management": disease_plan}
