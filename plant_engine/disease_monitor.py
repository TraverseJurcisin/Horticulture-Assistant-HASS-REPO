"""Disease threshold monitoring utilities."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries
from .disease_manager import recommend_treatments, recommend_prevention
from . import environment_manager

DATA_FILE = "disease_thresholds.json"
MONITOR_INTERVAL_FILE = "disease_monitoring_intervals.json"
RISK_FACTOR_FILE = "disease_risk_factors.json"

# Cached dataset
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)
# Recommended days between scouting events per plant stage
_MONITOR_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(MONITOR_INTERVAL_FILE)
_RISK_FACTORS: Dict[str, Dict[str, Dict[str, list]]] = load_dataset(RISK_FACTOR_FILE)

__all__ = [
    "list_supported_plants",
    "get_disease_thresholds",
    "assess_disease_pressure",
    "classify_disease_severity",
    "recommend_threshold_actions",
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

    data = _MONITOR_INTERVALS.get(normalize_key(plant_type), {})
    if stage:
        value = data.get(normalize_key(stage))
        if isinstance(value, (int, float)):
            return int(value)
    value = data.get("optimal")
    if isinstance(value, (int, float)):
        return int(value)
    return None


def next_monitor_date(
    plant_type: str, stage: str | None, last_date: date
) -> date | None:
    """Return the next disease scouting date based on guidelines."""

    interval = get_monitoring_interval(plant_type, stage)
    if interval is None:
        return None
    return last_date + timedelta(days=interval)


def generate_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[date]:
    """Return list of upcoming disease monitoring dates."""
    interval = get_monitoring_interval(plant_type, stage)
    if interval is None or events <= 0:
        return []
    return [start + timedelta(days=interval * i) for i in range(1, events + 1)]


@dataclass
class DiseaseReport:
    """Consolidated disease monitoring report."""

    severity: Dict[str, str]
    thresholds_exceeded: Dict[str, bool]
    treatments: Dict[str, str]
    prevention: Dict[str, str]
    risk_levels: Dict[str, str]

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def generate_disease_report(
    plant_type: str,
    observations: Mapping[str, int],
    environment: Mapping[str, float] | None = None,
) -> Dict[str, object]:
    """Return severity, treatment, prevention and risk assessments."""
    severity = classify_disease_severity(plant_type, observations)
    thresholds = assess_disease_pressure(plant_type, observations)
    treatments = recommend_threshold_actions(plant_type, observations)
    prevention = recommend_prevention(plant_type, observations.keys())
    risk = estimate_disease_risk(plant_type, environment) if environment else {}
    report = DiseaseReport(
        severity=severity,
        thresholds_exceeded=thresholds,
        treatments=treatments,
        prevention=prevention,
        risk_levels=risk,
    )
    return report.as_dict()
