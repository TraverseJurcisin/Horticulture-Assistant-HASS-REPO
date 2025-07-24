"""Disease threshold monitoring utilities."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries
from .monitor_utils import get_interval as _get_interval, next_date as _next_date, generate_schedule as _generate_schedule
from .disease_manager import recommend_treatments, recommend_prevention
from . import environment_manager

DATA_FILE = "disease_thresholds.json"
MONITOR_INTERVAL_FILE = "disease_monitoring_intervals.json"
RISK_DATA_FILE = "disease_risk_factors.json"
SEVERITY_ACTIONS_FILE = "disease_severity_actions.json"

# Cached dataset
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)
# Recommended days between scouting events per plant stage
_MONITOR_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(MONITOR_INTERVAL_FILE)
_RISK_FACTORS: Dict[str, Dict[str, Dict[str, list]]] = load_dataset(RISK_DATA_FILE)
_SEVERITY_ACTIONS: Dict[str, str] = load_dataset(SEVERITY_ACTIONS_FILE)

__all__ = [
    "list_supported_plants",
    "get_disease_thresholds",
    "assess_disease_pressure",
    "classify_disease_severity",
    "recommend_threshold_actions",
    "get_severity_action",
    "estimate_disease_risk",
    "get_monitoring_interval",
    "next_monitor_date",
    "generate_monitoring_schedule",
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


def estimate_disease_risk(
    plant_type: str, environment: Mapping[str, float]
) -> Dict[str, str]:
    """Return disease risk level based on environmental conditions."""

    factors = _RISK_FACTORS.get(normalize_key(plant_type), {})
    if not factors:
        return {}

    readings = environment_manager.normalize_environment_readings(environment)
    risks: Dict[str, str] = {}
    for disease, reqs in factors.items():
        matches = 0
        total = 0
        for key, (low, high) in reqs.items():
            total += 1
            value = readings.get(key)
            if value is None:
                continue
            if low <= value <= high:
                matches += 1
        if total == 0:
            continue
        if matches == 0:
            level = "low"
        elif matches < total:
            level = "moderate"
        else:
            level = "high"
        risks[disease] = level
    return risks


def get_monitoring_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between disease scouting events."""

    return _get_interval(_MONITOR_INTERVALS, plant_type, stage)


def next_monitor_date(
    plant_type: str, stage: str | None, last_date: date
) -> date | None:
    """Return the next disease scouting date based on guidelines."""

    return _next_date(_MONITOR_INTERVALS, plant_type, stage, last_date)


def generate_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[date]:
    """Return list of upcoming disease monitoring dates."""
    return _generate_schedule(_MONITOR_INTERVALS, plant_type, stage, start, events)


def get_severity_action(level: str) -> str:
    """Return recommended action for a severity ``level``."""

    return _SEVERITY_ACTIONS.get(level.lower(), "")


@dataclass
class DiseaseReport:
    """Consolidated disease monitoring report."""

    severity: Dict[str, str]
    thresholds_exceeded: Dict[str, bool]
    treatments: Dict[str, str]
    prevention: Dict[str, str]
    severity_actions: Dict[str, str]

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def generate_disease_report(plant_type: str, observations: Mapping[str, int]) -> Dict[str, object]:
    """Return severity, treatment and prevention recommendations."""
    severity = classify_disease_severity(plant_type, observations)
    thresholds = assess_disease_pressure(plant_type, observations)
    treatments = recommend_threshold_actions(plant_type, observations)
    prevention = recommend_prevention(plant_type, observations.keys())
    severity_actions = {d: get_severity_action(lvl) for d, lvl in severity.items()}
    report = DiseaseReport(
        severity=severity,
        thresholds_exceeded=thresholds,
        treatments=treatments,
        prevention=prevention,
        severity_actions=severity_actions,
    )
    return report.as_dict()
