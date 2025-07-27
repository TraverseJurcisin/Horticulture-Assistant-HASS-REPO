"""Advanced nutrient adjustment utilities."""

from __future__ import annotations

from typing import Mapping, Iterable, Dict

from .nutrient_manager import (
    get_all_recommended_levels,
    apply_tag_modifiers,
)
from .nutrient_manager import get_all_ph_adjusted_levels
from .root_temperature import adjust_uptake

__all__ = [
    "optimize_targets",
    "recommend_adjustments",
]


def optimize_targets(
    plant_type: str,
    stage: str,
    *,
    ph: float | None = None,
    root_temp_c: float | None = None,
    tags: Iterable[str] | None = None,
) -> Dict[str, float]:
    """Return nutrient targets adjusted for pH, root temperature and tags."""

    targets = get_all_recommended_levels(plant_type, stage)
    if tags:
        targets = apply_tag_modifiers(targets, tags)
    if ph is not None:
        targets = get_all_ph_adjusted_levels(plant_type, stage, ph)
        if tags:
            targets = apply_tag_modifiers(targets, tags)
    if root_temp_c is not None:
        targets = adjust_uptake(targets, root_temp_c)
    return targets


def recommend_adjustments(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    *,
    ph: float | None = None,
    root_temp_c: float | None = None,
    tags: Iterable[str] | None = None,
) -> Dict[str, float]:
    """Return ppm adjustments to meet optimized nutrient targets."""

    targets = optimize_targets(
        plant_type,
        stage,
        ph=ph,
        root_temp_c=root_temp_c,
        tags=tags,
    )

    adjustments: Dict[str, float] = {}
    for nutrient, target in targets.items():
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        delta = round(target - current, 2)
        if delta > 0:
            adjustments[nutrient] = delta
    return adjustments
