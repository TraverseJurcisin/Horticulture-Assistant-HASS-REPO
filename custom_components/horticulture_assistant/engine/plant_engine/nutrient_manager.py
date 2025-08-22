"""Utility helpers for nutrient recommendation and analysis."""
from __future__ import annotations

from typing import Dict, Mapping, Iterable

from .constants import get_stage_multiplier

from .utils import (
    load_dataset,
    normalize_key,
    list_dataset_entries,
    clear_dataset_cache,
)
from .nutrient_availability import availability_for_all

DATA_FILE = "nutrients/nutrient_guidelines.json"
RATIO_DATA_FILE = "nutrients/nutrient_ratio_guidelines.json"
WEIGHT_DATA_FILE = "nutrients/nutrient_weights.json"
TAG_MODIFIER_FILE = "nutrients/nutrient_tag_modifiers.json"


# Ensure dataset cache respects overlay changes on reload
clear_dataset_cache()
# Dataset cached via :func:`load_dataset` so this only happens once
_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(DATA_FILE)
_RATIO_DATA: Dict[str, Dict[str, Dict[str, float]]] = load_dataset(RATIO_DATA_FILE)
_WEIGHTS: Dict[str, float] = load_dataset(WEIGHT_DATA_FILE)
_RAW_TAG_MODIFIERS: Dict[str, Dict[str, float]] = load_dataset(TAG_MODIFIER_FILE)
# Normalize modifier keys for consistent lookups regardless of hyphen/space use
_TAG_MODIFIERS: Dict[str, Dict[str, float]] = {
    normalize_key(k): v for k, v in _RAW_TAG_MODIFIERS.items()
} if isinstance(_RAW_TAG_MODIFIERS, dict) else {}

__all__ = [
    "list_supported_plants",
    "get_recommended_levels",
    "get_all_recommended_levels",
    "get_stage_adjusted_levels",
    "get_all_stage_adjusted_levels",
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
    "calculate_deficiency_index",
    "calculate_deficiency_index_series",
    "recommend_ratio_adjustments",
    "calculate_nutrient_adjustments",
    "get_tag_modifier",
    "apply_tag_modifiers",
    "get_ph_adjusted_levels",
    "calculate_deficiencies_with_ph",
    "get_all_ph_adjusted_levels",
    "calculate_all_deficiencies_with_ph",
    "get_temperature_adjusted_levels",
    "calculate_cycle_deficiency_index",
    "calculate_deficiency_index_with_temperature",
    "get_synergy_adjusted_levels",
    "get_ph_synergy_adjusted_levels",
    "calculate_all_deficiencies_with_synergy",
    "calculate_all_deficiencies_with_ph_and_synergy",
    "calculate_deficiency_index_with_synergy",
    "calculate_deficiency_index_with_ph",
    "calculate_deficiency_index_with_ph_and_synergy",
    "get_environment_adjusted_levels",
    "calculate_deficiency_index_environment_adjusted",
]


def _calc_diff(
    current_levels: Mapping[str, float],
    targets: Mapping[str, float],
    *,
    mode: str,
) -> Dict[str, float]:
    """Return positive ppm differences between ``current_levels`` and ``targets``."""

    result: Dict[str, float] = {}
    for nutrient, target in targets.items():
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        delta = round(target - current, 2)
        if mode == "deficit" and delta > 0:
            result[nutrient] = delta
        elif mode == "surplus" and delta < 0:
            result[nutrient] = -delta
    return result


def _calc_balance(current_levels: Mapping[str, float], targets: Mapping[str, float]) -> Dict[str, float]:
    """Return ratio of ``current_levels`` to ``targets`` values."""

    ratios: Dict[str, float] = {}
    for nutrient, target in targets.items():
        if target <= 0:
            continue
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        ratios[nutrient] = round(current / target, 2)
    return ratios


def _deficiency_index_for_targets(current_levels: Mapping[str, float], targets: Mapping[str, float]) -> float:
    """Return deficiency index for ``current_levels`` against ``targets``."""

    total_weight = 0.0
    deficit_score = 0.0
    for nutrient, target in targets.items():
        if target <= 0:
            continue
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        deficit = max(target - current, 0.0) / target
        weight = get_nutrient_weight(nutrient)
        deficit_score += weight * deficit
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return round((deficit_score / total_weight) * 100, 1)


def get_nutrient_weight(nutrient: str) -> float:
    """Return importance weight for ``nutrient``.

    Values are read from :data:`nutrient_weights.json` once at module
    import time for better performance. The dataset can be reloaded by
    calling :func:`plant_engine.utils.clear_dataset_cache` and
    re-importing this module.
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


def get_stage_adjusted_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended levels scaled by the stage multiplier."""

    levels = get_recommended_levels(plant_type, stage)
    mult = get_stage_multiplier(stage)
    if mult == 1.0 or not levels:
        return levels
    return {n: round(v * mult, 2) for n, v in levels.items()}


def calculate_deficiencies(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient deficiencies compared to guidelines.

    Only nutrients below the recommended level are returned with the amount
    needed (ppm) to reach the target.
    """

    targets = get_recommended_levels(plant_type, stage)
    return _calc_diff(current_levels, targets, mode="deficit")


def calculate_nutrient_balance(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return ratio of current to recommended nutrient levels."""

    targets = get_recommended_levels(plant_type, stage)
    return _calc_balance(current_levels, targets)


def calculate_surplus(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
) -> Dict[str, float]:
    """Return nutrient amounts exceeding recommendations."""

    targets = get_recommended_levels(plant_type, stage)
    return _calc_diff(current_levels, targets, mode="surplus")


def calculate_nutrient_adjustments(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return ppm adjustments needed to meet recommended levels."""

    recommended = get_recommended_levels(plant_type, stage)
    adjustments: Dict[str, float] = {}
    for nutrient, target in recommended.items():
        try:
            current = float(current_levels.get(nutrient, 0.0))
        except (TypeError, ValueError):
            current = 0.0
        delta = round(target - current, 2)
        if delta != 0:
            adjustments[nutrient] = delta
    return adjustments


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


def calculate_deficiency_index(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> float:
    """Return a weighted 0-100 index of overall nutrient deficiency severity.

    A value of ``0`` indicates all nutrients meet or exceed the recommended
    levels while ``100`` means every nutrient is completely absent. Nutrient
    importance weights from :data:`nutrient_weights.json` are applied so more
    critical elements have a greater influence on the index.
    """

    targets = get_all_recommended_levels(plant_type, stage)
    if not targets:
        return 0.0

    return _deficiency_index_for_targets(current_levels, targets)


def calculate_deficiency_index_series(
    series: Iterable[Mapping[str, float]], plant_type: str, stage: str
) -> float:
    """Return the average deficiency index for a sequence of readings."""

    indices = [calculate_deficiency_index(s, plant_type, stage) for s in series]
    if not indices:
        return 0.0
    return round(sum(indices) / len(indices), 1)


def get_all_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return combined macro and micro nutrient guidelines."""

    base = get_recommended_levels(plant_type, stage)
    # ``get_recommended_levels`` returns the cached dataset mapping so we must
    # copy it before merging in micronutrient values to avoid mutating the
    # global dataset. Tests that call this helper previously polluted the shared
    # cache which later affected other lookups.
    levels = dict(base)

    from .micro_manager import get_recommended_levels as _micro

    levels.update(_micro(plant_type, stage))
    return levels


def get_all_stage_adjusted_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return macro and micro guidelines scaled by the stage multiplier."""

    levels = get_all_recommended_levels(plant_type, stage)
    mult = get_stage_multiplier(stage)
    if mult == 1.0 or not levels:
        return levels
    return {n: round(v * mult, 2) for n, v in levels.items()}


def calculate_all_deficiencies(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return overall nutrient deficiencies including micronutrients."""

    deficits = calculate_deficiencies(current_levels, plant_type, stage)
    from .micro_manager import calculate_deficiencies as _micro_def

    deficits.update(_micro_def(current_levels, plant_type, stage))
    return deficits


def calculate_all_surplus(
    current_levels: Mapping[str, float], plant_type: str, stage: str
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

    targets = get_all_recommended_levels(plant_type, stage)
    return _calc_balance(current_levels, targets)


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
    return _calc_diff(current_levels, targets, mode="deficit")


def get_all_ph_adjusted_levels(plant_type: str, stage: str, ph: float) -> Dict[str, float]:
    """Return macro and micro nutrient targets adjusted for solution pH."""

    targets = get_all_recommended_levels(plant_type, stage)
    if not targets:
        return {}

    if not 0 < ph <= 14:
        raise ValueError("ph must be between 0 and 14")

    factors = availability_for_all(ph)
    adjusted: Dict[str, float] = {}
    for nutrient, ppm in targets.items():
        factor = factors.get(nutrient, 1.0)
        adjusted[nutrient] = round(ppm / factor, 2) if factor > 0 else ppm
    return adjusted


def calculate_all_deficiencies_with_ph(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, float]:
    """Return overall deficiencies using pH-adjusted guidelines."""

    targets = get_all_ph_adjusted_levels(plant_type, stage, ph)
    return _calc_diff(current_levels, targets, mode="deficit")


def get_temperature_adjusted_levels(
    plant_type: str, stage: str, root_temp_c: float
) -> Dict[str, float]:
    """Return nutrient targets adjusted for root temperature uptake."""

    base = get_all_recommended_levels(plant_type, stage)
    if not base:
        return {}
    from .root_temperature import adjust_uptake

    return adjust_uptake(base, root_temp_c, plant_type)


def calculate_deficiency_index_with_temperature(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    root_temp_c: float,
) -> float:
    """Return deficiency index using temperature-adjusted nutrient targets."""

    targets = get_temperature_adjusted_levels(plant_type, stage, root_temp_c)
    if not targets:
        return calculate_deficiency_index(current_levels, plant_type, stage)

    return _deficiency_index_for_targets(current_levels, targets)


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


def calculate_cycle_deficiency_index(
    stage_levels: Mapping[str, Mapping[str, float]],
    plant_type: str,
) -> Dict[str, float]:
    """Return deficiency index for each growth stage in a cycle."""

    results: Dict[str, float] = {}
    for stage, levels in stage_levels.items():
        results[stage] = calculate_deficiency_index(levels, plant_type, stage)
    return results


def get_synergy_adjusted_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return nutrient targets adjusted using synergy factors."""

    levels = get_all_recommended_levels(plant_type, stage)
    if not levels:
        return {}
    from .nutrient_synergy import apply_synergy_adjustments

    return apply_synergy_adjustments(levels)


def get_ph_synergy_adjusted_levels(
    plant_type: str, stage: str, ph: float
) -> Dict[str, float]:
    """Return nutrient targets adjusted for synergy and solution pH."""

    if not 0 < ph <= 14:
        raise ValueError("ph must be between 0 and 14")

    levels = get_synergy_adjusted_levels(plant_type, stage)
    if not levels:
        levels = get_all_recommended_levels(plant_type, stage)

    factors = availability_for_all(ph)
    adjusted: Dict[str, float] = {}
    for nutrient, ppm in levels.items():
        factor = factors.get(nutrient, 1.0)
        adjusted[nutrient] = round(ppm / factor, 2) if factor > 0 else ppm
    return adjusted


def calculate_all_deficiencies_with_synergy(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, float]:
    """Return overall deficiencies using synergy-adjusted guidelines."""

    targets = get_synergy_adjusted_levels(plant_type, stage)
    return _calc_diff(current_levels, targets, mode="deficit")


def calculate_all_deficiencies_with_ph_and_synergy(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> Dict[str, float]:
    """Return deficiencies using synergy- and pH-adjusted targets."""

    targets = get_ph_synergy_adjusted_levels(plant_type, stage, ph)

    return _calc_diff(current_levels, targets, mode="deficit")


def calculate_deficiency_index_with_synergy(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> float:
    """Return deficiency index using synergy-adjusted nutrient targets."""

    targets = get_synergy_adjusted_levels(plant_type, stage)
    if not targets:
        return calculate_deficiency_index(current_levels, plant_type, stage)

    return _deficiency_index_for_targets(current_levels, targets)


def calculate_deficiency_index_with_ph(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> float:
    """Return deficiency index using pH-adjusted nutrient targets."""

    targets = get_all_ph_adjusted_levels(plant_type, stage, ph)
    if not targets:
        return calculate_deficiency_index(current_levels, plant_type, stage)

    return _deficiency_index_for_targets(current_levels, targets)


def calculate_deficiency_index_with_ph_and_synergy(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    ph: float,
) -> float:
    """Return deficiency index using synergy and pH adjusted targets."""

    targets = get_ph_synergy_adjusted_levels(plant_type, stage, ph)
    if not targets:
        return calculate_deficiency_index(current_levels, plant_type, stage)

    return _deficiency_index_for_targets(current_levels, targets)


def get_environment_adjusted_levels(
    plant_type: str,
    stage: str,
    *,
    ph: float | None = None,
    root_temp_c: float | None = None,
    synergy: bool = False,
) -> Dict[str, float]:
    """Return nutrient targets adjusted for synergy, pH and temperature."""

    levels = get_all_recommended_levels(plant_type, stage)
    if not levels:
        return {}

    if synergy:
        from .nutrient_synergy import apply_synergy_adjustments

        levels = apply_synergy_adjustments(levels)

    if ph is not None:
        if not 0 < ph <= 14:
            raise ValueError("ph must be between 0 and 14")
        factors = availability_for_all(ph)
        levels = {
            n: round(v / factors.get(n, 1.0), 2)
            for n, v in levels.items()
            if v is not None
        }

    if root_temp_c is not None:
        from .root_temperature import adjust_uptake

        levels = adjust_uptake(levels, root_temp_c, plant_type)

    return levels


def calculate_deficiency_index_environment_adjusted(
    current_levels: Mapping[str, float],
    plant_type: str,
    stage: str,
    *,
    ph: float | None = None,
    root_temp_c: float | None = None,
    synergy: bool = False,
) -> float:
    """Return deficiency index using environment-adjusted targets."""

    targets = get_environment_adjusted_levels(
        plant_type, stage, ph=ph, root_temp_c=root_temp_c, synergy=synergy
    )
    if not targets:
        return calculate_deficiency_index(current_levels, plant_type, stage)
    return _deficiency_index_for_targets(current_levels, targets)
