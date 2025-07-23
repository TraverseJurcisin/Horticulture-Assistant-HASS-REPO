"""Disease threshold monitoring utilities."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries
from .disease_manager import recommend_treatments, recommend_prevention

DATA_FILE = "disease_thresholds.json"

# Cached dataset
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_disease_thresholds",
    "assess_disease_pressure",
    "classify_disease_severity",
    "recommend_threshold_actions",
    "generate_disease_report",
    "DiseaseReport",
]


def list_supported_plants() -> list[str]:
    """Return plant types with disease threshold data."""
    return list_dataset_entries(_THRESHOLDS)


def get_disease_thresholds(plant_type: str) -> Dict[str, int]:
    """Return disease count thresholds for ``plant_type`` with normalized keys."""
    raw = _THRESHOLDS.get(normalize_key(plant_type), {})
    return {normalize_key(k): int(v) for k, v in raw.items()}


def assess_disease_pressure(plant_type: str, observations: Mapping[str, int]) -> Dict[str, bool]:
    """Return mapping of diseases to ``True`` if counts exceed thresholds."""
    thresholds = get_disease_thresholds(plant_type)
    pressure: Dict[str, bool] = {}
    for name, count in observations.items():
        key = normalize_key(name)
        thresh = thresholds.get(key)
        if thresh is None:
            continue
        pressure[key] = count >= thresh
    return pressure


def classify_disease_severity(plant_type: str, observations: Mapping[str, int]) -> Dict[str, str]:
    """Return ``low``, ``moderate`` or ``severe`` classifications."""
    thresholds = get_disease_thresholds(plant_type)
    severity: Dict[str, str] = {}
    for name, count in observations.items():
        key = normalize_key(name)
        thresh = thresholds.get(key)
        if thresh is None:
            continue
        if count < thresh:
            level = "low"
        elif count < thresh * 2:
            level = "moderate"
        else:
            level = "severe"
        severity[key] = level
    return severity


def recommend_threshold_actions(plant_type: str, observations: Mapping[str, int]) -> Dict[str, str]:
    """Return treatment actions for diseases exceeding thresholds."""
    pressure = assess_disease_pressure(plant_type, observations)
    exceeded = [name for name in observations if pressure.get(normalize_key(name))]
    if not exceeded:
        return {}
    return recommend_treatments(plant_type, exceeded)


@dataclass
class DiseaseReport:
    """Consolidated disease monitoring report."""

    severity: Dict[str, str]
    thresholds_exceeded: Dict[str, bool]
    treatments: Dict[str, str]
    prevention: Dict[str, str]

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def generate_disease_report(plant_type: str, observations: Mapping[str, int]) -> Dict[str, object]:
    """Return severity, treatment and prevention recommendations."""
    severity = classify_disease_severity(plant_type, observations)
    thresholds = assess_disease_pressure(plant_type, observations)
    treatments = recommend_threshold_actions(plant_type, observations)
    prevention = recommend_prevention(plant_type, observations.keys())
    report = DiseaseReport(
        severity=severity,
        thresholds_exceeded=thresholds,
        treatments=treatments,
        prevention=prevention,
    )
    return report.as_dict()
