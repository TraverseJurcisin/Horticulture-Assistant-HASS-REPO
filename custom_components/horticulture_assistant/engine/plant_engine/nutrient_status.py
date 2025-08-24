"""Utilities for classifying nutrient levels.

This module combines deficiency and toxicity checks to provide a simple
status label for each nutrient. Possible labels are ``"adequate"``,
``"mild deficiency"``, ``"moderate deficiency"``, ``"severe deficiency``" and
``"excessive"``.
"""

from __future__ import annotations

from collections.abc import Mapping

from .deficiency_manager import (
    calculate_deficiencies,
    classify_deficiency_levels,
)
from .nutrient_manager import get_all_recommended_levels
from .toxicity_manager import check_toxicities

__all__ = ["classify_nutrient_status"]


def classify_nutrient_status(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> dict[str, str]:
    """Return classification of nutrient levels for a plant stage.

    Parameters
    ----------
    current_levels : Mapping[str, float]
        Current nutrient concentrations in ppm.
    plant_type : str
        Crop identifier for guideline lookups.
    stage : str
        Growth stage used for nutrient targets.

    Returns
    -------
    Dict[str, str]
        Mapping of nutrient codes to status labels.
    """

    recommended = get_all_recommended_levels(plant_type, stage)
    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    severity = classify_deficiency_levels(deficits)
    toxic = check_toxicities(current_levels, plant_type)

    status: dict[str, str] = {}
    for nutrient in recommended:
        if nutrient in toxic:
            status[nutrient] = "excessive"
            continue
        level = severity.get(nutrient)
        if level:
            status[nutrient] = f"{level} deficiency"
        else:
            status[nutrient] = "adequate"
    return status
