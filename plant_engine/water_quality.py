"""Water quality interpretation helpers."""

from __future__ import annotations

from typing import Dict, Tuple

from .utils import load_dataset

DATA_FILE = "water_quality_thresholds.json"

# Cached thresholds loaded once via :func:`load_dataset`
_THRESHOLDS: Dict[str, float] = load_dataset(DATA_FILE)

__all__ = [
    "list_analytes",
    "get_threshold",
    "interpret_water_profile",
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
