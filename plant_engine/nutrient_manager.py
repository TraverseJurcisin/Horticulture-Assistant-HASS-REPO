"""Utility helpers for nutrient recommendation and analysis."""
from __future__ import annotations

from typing import Dict, Mapping, Iterable

from .utils import (
    load_dataset,
    normalize_key,
    list_dataset_entries,
    clear_dataset_cache,
)
from .nutrient_availability import availability_factor, availability_for_all

DATA_FILE = "nutrient_guidelines.json"
RATIO_DATA_FILE = "nutrient_ratio_guidelines.json"
WEIGHT_DATA_FILE = "nutrient_weights.json"
TAG_MODIFIER_FILE = "nutrient_tag_modifiers.json"


# Ensure dataset cache respects overlay changes on reload
clear_dataset_cache()
# Dataset cached via :func:`load_dataset` so this only happens once
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)
_RATIO_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(RATIO_DATA_FILE)
_WEIGHTS: Dict[str, float] = load_dataset(WEIGHT_DATA_FILE)
_TAG_MODIFIERS: Dict[str, Dict[str, float]] = load_dataset(TAG_MODIFIER_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "get_all_recommended_levels",
    "calculate_deficiencies",
    "calculate_all_deficiencies",
    "calculate_nutrient_balance",
    "calculate_surplus",
    "calculate_all_surplus",
    "calculate_all_nutrient_balance",
    "get_npk_ratio",
    "get_stage_ratio",
    "get_nutrient_weight",
    "score_nutrient_levels",
    "score_nutrient_series",
    "recommend_ratio_adjustments",
    "get_tag_modifier",
    "apply_tag_modifiers",
    "get_ph_adjusted_levels",
    "calculate_deficiencies_with_ph",
]


def get_nutrient_weight(nutrient: str) -> float:
    """Return importance weight for a nutrient.

    If no weight is defined the default ``1.0`` is returned.
    """

    try:
        return float(_WEIGHTS.get(nutrient, 1.0))
    except (TypeError, ValueError):
        return 1.0


def list_supported_plants() -> list[str]:
    """Return all plant types with nutrient guidelines."""
    return list_dataset_entries(_DATA)


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient levels for ``plant_type`` and ``stage``.

    Parameters are normalized using :func:`normalize_key` so lookups are
    case-insensitive and spaces are ignored. If no guidelines exist the
    function returns an empty dictionary.
    """

    plant = _DATA.get(normalize_key(plant_type))
    if not plant:
        return {}
    return plant.get(normalize_key(stage), {})


def calculate_deficiencies(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient deficiencies compared to guidelines.

    Only nutrients below the recommended level are returned with the amount
    needed (ppm) to reach the target.
    """

    recommended = get_recommended_levels(plant_type, stage)
    deficiencies: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        current = current_levels.get(nutrient, 0.0)
        diff = round(target - current, 2)
        if diff > 0:
            deficiencies[nutrient] = diff
    return deficiencies


def calculate_nutrient_balance(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return ratio of current to recommended nutrient levels."""

    recommended = get_recommended_levels(plant_type, stage)
    ratios: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        if target <= 0:
            continue
        current = current_levels.get(nutrient, 0.0)
        ratios[nutrient] = round(current / target, 2)
    return ratios


def calculate_surplus(
    current_levels: Dict[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient amounts exceeding recommendations."""

    recommended = get_recommended_levels(plant_type, stage)
    surplus: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        current = current_levels.get(nutrient, 0.0)
        diff = round(current - target, 2)
        if diff > 0:
            surplus[nutrient] = diff
    return surplus


def get_npk_ratio(plant_type: str, stage: str) -> Dict[str, float]:
    """Return normalized N:P:K ratio for a plant stage.

    The ratios sum to 1.0. If any nutrient is missing or all values are zero,
    ``{"N": 0.0, "P": 0.0, "K": 0.0}`` is returned.
    """

    rec = get_recommended_levels(plant_type, stage)
    n = rec.get("N", 0.0)
    p = rec.get("P", 0.0)
    k = rec.get("K", 0.0)
    total = n + p + k
    if total <= 0:
        return {"N": 0.0, "P": 0.0, "K": 0.0}

    return {
        "N": round(n / total, 2),
        "P": round(p / total, 2),
        "K": round(k / total, 2),
    }


def get_stage_ratio(plant_type: str, stage: str) -> Dict[str, float]:
    """Return NPK ratio from :data:`nutrient_ratio_guidelines.json` if available."""

    plant = _RATIO_DATA.get(normalize_key(plant_type))
    if plant and normalize_key(stage) in plant:
        ratios = plant[normalize_key(stage)]
        total = sum(float(v) for v in ratios.values() if v)
        if total > 0:
            return {k: round(float(v) / total, 2) for k, v in ratios.items()}

    return get_npk_ratio(plant_type, stage)


def score_nutrient_levels(
    current_levels: Dict[str, float], plant_type: str, stage: str
) -> float:
    """Return a 0-100 score for how close ``current_levels`` are to guidelines.

    Nutrients can be assigned importance weights in
    :data:`nutrient_weights.json`. Unknown nutrients default to ``1.0``.
    A perfect match yields ``100`` while values more than double or less than
    zero of the target contribute ``0`` to the overall score.
    """

    recommended = get_recommended_levels(plant_type, stage)
    if not recommended:
        return 0.0

    score = 0.0
    total_weight = 0.0
    for nutrient, target in recommended.items():
        if target <= 0:
            continue
        current = current_levels.get(nutrient)
        if current is None:
            continue
        diff_ratio = abs(current - target) / target
        weight = get_nutrient_weight(nutrient)
        score += weight * max(0.0, 1 - diff_ratio)
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return round((score / total_weight) * 100, 1)


def score_nutrient_series(
    series: Iterable[Mapping[str, float]], plant_type: str, stage: str
) -> float:
    """Return the average nutrient score for a sequence of readings."""

    scores = [score_nutrient_levels(s, plant_type, stage) for s in series]
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 1)


def get_all_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return combined macro and micro nutrient guidelines."""

    levels = get_recommended_levels(plant_type, stage)
    from .micro_manager import get_recommended_levels as _micro

    levels.update(_micro(plant_type, stage))
    return levels


def calculate_all_deficiencies(
    current_levels: Dict[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return overall nutrient deficiencies including micronutrients."""

    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    from .micro_manager import calculate_deficiencies as _micro_def

    deficits.update(_micro_def(current_levels, plant_type, stage))
    return deficits


def calculate_all_surplus(
    current_levels: Dict[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return overall nutrient surplus including micronutrients."""

    surplus = calculate_surplus(current_levels, plant_type, stage)
    from .micro_manager import calculate_surplus as _micro_surplus

    surplus.update(_micro_surplus(current_levels, plant_type, stage))
    return surplus


def calculate_all_nutrient_balance(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return ratio of current to recommended levels for all nutrients."""

    recommended = get_all_recommended_levels(plant_type, stage)
    ratios: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        if target <= 0:
            continue
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            continue
        ratios[nutrient] = round(current / target, 2)
    return ratios


def get_ph_adjusted_levels(plant_type: str, stage: str, ph: float) -> Dict[str, float]:
    """Return nutrient targets adjusted for solution pH availability.

    Parameters
    ----------
    plant_type : str
        Crop identifier used to look up nutrient guidelines.
    stage : str
        Growth stage for guideline lookup.
    ph : float
        Solution pH value. Must be within the standard 0-14 range.
    """

    if not 0 < ph <= 14:
        raise ValueError("ph must be between 0 and 14")

    targets = get_recommended_levels(plant_type, stage)
    if not targets:
        return {}

    factors = availability_for_all(ph)
    adjusted: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        factor = factors.get(nutrient, 1.0)
        if factor <= 0:
            adjusted[nutrient] = ppm
        else:
            adjusted[nutrient] = round(ppm / factor, 2)
    return adjusted


def calculate_deficiencies_with_ph(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, float]:
    """Return deficiencies using pH-adjusted nutrient targets."""

    targets = get_ph_adjusted_levels(plant_type, stage, ph)
    deficits: Dict[str, float] = {}
    for nutrient, target in targets.items():
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        diff = round(target - current, 2)
        if diff > 0:
            deficits[nutrient] = diff
    return deficits


def recommend_ratio_adjustments(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    *,
    total_ppm: float | None = None,
    tolerance: float = 0.05,
) -> Dict[str, float]:
    """Return ppm adjustments to achieve the recommended NPK ratio.

    Parameters
    ----------
    current_levels : Mapping[str, float]
        Current nutrient concentration in ppm.
    plant_type : str
        Crop identifier used for ratio guidelines.
    stage : str
        Growth stage for ratio lookup.
    total_ppm : float, optional
        Total NPK ppm to use for calculating target amounts. When ``None`` the
        sum of current N, P and K levels is used.
    tolerance : float, optional
        Minimum fractional difference before an adjustment is returned.

    Returns
    -------
    Dict[str, float]
        Mapping of nutrient codes to positive (add) or negative (remove) ppm
        values needed to achieve the guideline ratio.
    """

    target_ratio = get_stage_ratio(plant_type, stage)
    if not target_ratio:
        return {}

    if total_ppm is None:
        total_ppm = sum(float(current_levels.get(n, 0.0)) for n in ("N", "P", "K"))
    if total_ppm <= 0:
        return {}

    adjustments: Dict[str, float] = {}
    for nutrient in ("N", "P", "K"):
        target_ppm = target_ratio.get(nutrient, 0.0) * total_ppm
        current_ppm = float(current_levels.get(nutrient, 0.0))
        delta = target_ppm - current_ppm
        if abs(delta) / total_ppm > tolerance:
            adjustments[nutrient] = round(delta, 2)

    return adjustments


def get_tag_modifier(tag: str) -> Dict[str, float]:
    """Return nutrient multipliers for ``tag`` if defined."""
    return _TAG_MODIFIERS.get(normalize_key(tag), {})


def apply_tag_modifiers(
    targets: Mapping[str, float], tags: Iterable[str]
) -> Dict[str, float]:
    """Return ``targets`` adjusted by modifiers for each tag."""

    adjusted = {k: float(v) for k, v in targets.items()}
    for tag in tags:
        mods = get_tag_modifier(tag)
        if not mods:
            continue
        for nutrient, factor in mods.items():
            if nutrient not in adjusted:
                continue
            try:
                adjusted[nutrient] = round(adjusted[nutrient] * float(factor), 2)
            except (TypeError, ValueError):
                continue
    return adjusted


