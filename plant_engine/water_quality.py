"""Water quality interpretation helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Tuple, Mapping, Any

from .utils import lazy_dataset, list_dataset_entries, normalize_key

DATA_FILE = "water/water_quality_thresholds.json"
ACTION_FILE = "water/water_quality_actions.json"
SALINITY_FILE = "water/water_salinity_tolerance.json"

# Cached thresholds loaded once via :func:`load_dataset`
_thresholds = lazy_dataset(DATA_FILE)
_actions = lazy_dataset(ACTION_FILE)
_salinity_limits = lazy_dataset(SALINITY_FILE)

__all__ = [
    "list_analytes",
    "get_threshold",
    "interpret_water_profile",
    "classify_water_quality",
    "score_water_quality",
    "recommend_treatments",
    "summarize_water_profile",
    "blend_water_profiles",
    "max_safe_blend_ratio",
    "list_salinity_plants",
    "get_salinity_limit",
    "WaterProfileSummary",
]


@dataclass(slots=True, frozen=True)
class WaterProfileSummary:
    """Summary of irrigation water quality analysis."""

    baseline: Dict[str, float]
    warnings: Dict[str, Dict[str, float]]
    rating: str
    score: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def list_analytes() -> list[str]:
    """Return all analytes with defined thresholds."""
    return sorted(_thresholds().keys())


def get_threshold(analyte: str) -> float | None:
    """Return the toxicity threshold for ``analyte`` if defined."""
    return _thresholds().get(analyte)


def interpret_water_profile(water_test: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    """Return baseline nutrients and warnings for a water quality profile."""
    baseline: Dict[str, float] = {}
    warnings: Dict[str, Dict[str, float]] = {}

    for ion, value in water_test.items():
        baseline[ion] = value
        limit = _thresholds().get(ion)
        if limit is not None and value > limit:
            warnings[ion] = {
                "value": value,
                "limit": limit,
                "issue": "Exceeds safe threshold",
            }

    return baseline, warnings


def classify_water_quality(water_test: Dict[str, float]) -> str:
    """Return a simple quality rating for ``water_test``.

    The rating is ``"good"`` when no analyte exceeds its threshold,
    ``"fair"`` when one or two exceed, and ``"poor"`` otherwise.
    """

    _, warnings = interpret_water_profile(water_test)
    count = len(warnings)
    if count == 0:
        return "good"
    if count <= 2:
        return "fair"
    return "poor"


def score_water_quality(water_test: Dict[str, float]) -> float:
    """Return a 0-100 score based on threshold exceedances."""
    score = 100.0
    for ion, limit in _thresholds().items():
        if ion not in water_test:
            continue
        value = water_test[ion]
        if value <= limit:
            continue
        exceed_ratio = (value - limit) / limit
        penalty = min(exceed_ratio, 1.0) * 25
        score -= penalty
    return round(max(score, 0.0), 1)

def recommend_treatments(water_test: Dict[str, float]) -> Dict[str, str]:
    """Return recommended remediation steps for analytes exceeding thresholds."""
    _, warnings = interpret_water_profile(water_test)
    recommendations: Dict[str, str] = {}
    for analyte in warnings:
        action = _actions().get(analyte)
        if action:
            recommendations[analyte] = action
    return recommendations


def summarize_water_profile(water_test: Mapping[str, float]) -> WaterProfileSummary:
    """Return baseline, warnings, rating and score for ``water_test``."""

    baseline, warnings = interpret_water_profile(dict(water_test))
    return WaterProfileSummary(
        baseline=baseline,
        warnings=warnings,
        rating=classify_water_quality(baseline),
        score=score_water_quality(baseline),
    )


def blend_water_profiles(
    source_a: Mapping[str, float], source_b: Mapping[str, float], ratio_a: float
) -> Dict[str, float]:
    """Return analyte levels for a blend of two water sources.

    ``ratio_a`` indicates the fraction of ``source_a`` in the final mix. Any
    analytes absent from a source are treated as ``0.0``.
    """

    if ratio_a < 0 or ratio_a > 1:
        raise ValueError("ratio_a must be between 0 and 1")

    result: Dict[str, float] = {}
    ions = set(source_a) | set(source_b)
    for ion in ions:
        val_a = float(source_a.get(ion, 0.0))
        val_b = float(source_b.get(ion, 0.0))
        result[ion] = val_a * ratio_a + val_b * (1 - ratio_a)
    return result


def max_safe_blend_ratio(source_a: Mapping[str, float], source_b: Mapping[str, float]) -> float:
    """Return maximum fraction of ``source_a`` keeping all analytes below thresholds.

    The return value is constrained to ``0.0`` - ``1.0``. When no blend can
    satisfy the thresholds, ``0.0`` is returned.
    """

    ratio = 1.0
    for ion, limit in _thresholds().items():
        if ion not in source_a or ion not in source_b:
            continue
        a_val = float(source_a[ion])
        b_val = float(source_b[ion])
        if a_val <= limit and b_val <= limit:
            continue
        if a_val == b_val:
            if a_val > limit:
                ratio = 0.0
            continue
        try:
            req = (limit - b_val) / (a_val - b_val)
        except ZeroDivisionError:
            req = 0.0
        ratio = min(ratio, req)

    if ratio < 0 or not ratio:
        return 0.0
    return max(0.0, min(1.0, ratio))


def list_salinity_plants() -> list[str]:
    """Return plant types with irrigation water salinity data."""

    return list_dataset_entries(_salinity_limits())


def get_salinity_limit(plant_type: str) -> float | None:
    """Return maximum EC for irrigation water tolerated by ``plant_type``."""

    value = _salinity_limits().get(normalize_key(plant_type))
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
