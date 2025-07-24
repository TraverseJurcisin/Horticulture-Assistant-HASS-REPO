"""Water quality interpretation helpers."""

from __future__ import annotations

from typing import Dict, Tuple, Mapping, Any

from .utils import load_dataset

DATA_FILE = "water_quality_thresholds.json"
ACTION_FILE = "water_quality_actions.json"

# Cached thresholds loaded once via :func:`load_dataset`
_THRESHOLDS: Dict[str, float] = load_dataset(DATA_FILE)
_ACTIONS: Dict[str, str] = load_dataset(ACTION_FILE)

__all__ = [
    "list_analytes",
    "get_threshold",
    "interpret_water_profile",
    "classify_water_quality",
    "score_water_quality",
    "recommend_treatments",
    "summarize_water_profile",
]


def list_analytes() -> list[str]:
    """Return all analytes with defined thresholds."""
    return sorted(_THRESHOLDS.keys())


def get_threshold(analyte: str) -> float | None:
    """Return the toxicity threshold for ``analyte`` if defined."""
    return _THRESHOLDS.get(analyte)


def interpret_water_profile(water_test: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    """Return baseline nutrients and warnings for a water quality profile."""
    baseline: Dict[str, float] = {}
    warnings: Dict[str, Dict[str, float]] = {}

    for ion, value in water_test.items():
        baseline[ion] = value
        limit = _THRESHOLDS.get(ion)
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
    for ion, limit in _THRESHOLDS.items():
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
        action = _ACTIONS.get(analyte)
        if action:
            recommendations[analyte] = action
    return recommendations


def summarize_water_profile(water_test: Mapping[str, float]) -> Dict[str, Any]:
    """Return baseline, warnings, rating and score for ``water_test``."""

    baseline, warnings = interpret_water_profile(dict(water_test))
    return {
        "baseline": baseline,
        "warnings": warnings,
        "rating": classify_water_quality(baseline),
        "score": score_water_quality(baseline),
    }
