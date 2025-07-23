"""Pest monitoring utilities using threshold datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict, Mapping

from . import environment_manager

from .utils import load_dataset, normalize_key, list_dataset_entries
from .pest_manager import recommend_treatments, recommend_beneficials

DATA_FILE = "pest_thresholds.json"
RISK_DATA_FILE = "pest_risk_factors.json"
SEVERITY_ACTIONS_FILE = "pest_severity_actions.json"
# Recommended days between scouting events
MONITOR_INTERVAL_FILE = "pest_monitoring_intervals.json"

# Load once with caching
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)
_RISK_FACTORS: Dict[str, Dict[str, Dict[str, list]]] = load_dataset(RISK_DATA_FILE)
_SEVERITY_ACTIONS: Dict[str, str] = load_dataset(SEVERITY_ACTIONS_FILE)
_MONITOR_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(MONITOR_INTERVAL_FILE)

__all__ = [
    "list_supported_plants",
    "get_pest_thresholds",
    "assess_pest_pressure",
    "classify_pest_severity",
    "recommend_threshold_actions",
    "recommend_biological_controls",
    "estimate_pest_risk",
    "generate_pest_report",
    "get_severity_action",
    "get_monitoring_interval",
    "next_monitor_date",
    "generate_monitoring_schedule",
    "PestReport",
]


def get_pest_thresholds(plant_type: str) -> Dict[str, int]:
    """Return pest count thresholds for ``plant_type``.

    Lookup is case-insensitive and spaces are ignored so ``"Citrus"`` and
    ``"citrus"`` map to the same dataset entry.
    """

    return _THRESHOLDS.get(normalize_key(plant_type), {})


def list_supported_plants() -> list[str]:
    """Return plant types with pest threshold definitions."""

    return list_dataset_entries(_THRESHOLDS)


def get_monitoring_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between scouting events for a plant stage."""

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
    """Return the next pest scouting date based on interval guidelines."""

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
    """Return list of upcoming monitoring dates.

    If ``events`` is 0 or no interval is defined, an empty list is returned.
    """
    interval = get_monitoring_interval(plant_type, stage)
    if interval is None or events <= 0:
        return []
    return [start + timedelta(days=interval * i) for i in range(1, events + 1)]


def get_severity_action(level: str) -> str:
    """Return recommended action for a severity ``level``."""

    return _SEVERITY_ACTIONS.get(level.lower(), "")


def assess_pest_pressure(plant_type: str, observations: Mapping[str, int]) -> Dict[str, bool]:
    """Return mapping of pests to ``True`` if threshold exceeded."""

    thresholds = get_pest_thresholds(plant_type)
    pressure: Dict[str, bool] = {}
    for pest, count in observations.items():
        key = normalize_key(pest)
        thresh = thresholds.get(key)
        if thresh is None:
            continue
        pressure[key] = count >= thresh
    return pressure


def recommend_threshold_actions(plant_type: str, observations: Mapping[str, int]) -> Dict[str, str]:
    """Return treatment actions for pests exceeding thresholds."""

    pressure = assess_pest_pressure(plant_type, observations)
    exceeded = [p for p, flag in pressure.items() if flag]
    if not exceeded:
        return {}
    return recommend_treatments(plant_type, exceeded)


def recommend_biological_controls(
    plant_type: str, observations: Mapping[str, int]
) -> Dict[str, list[str]]:
    """Return beneficial insects for pests exceeding thresholds."""

    pressure = assess_pest_pressure(plant_type, observations)
    exceeded = [p for p, flag in pressure.items() if flag]
    if not exceeded:
        return {}
    return recommend_beneficials(exceeded)


def estimate_pest_risk(
    plant_type: str, environment: Mapping[str, float]
) -> Dict[str, str]:
    """Return pest risk level based on environmental conditions."""

    factors = _RISK_FACTORS.get(normalize_key(plant_type), {})
    if not factors:
        return {}

    readings = environment_manager.normalize_environment_readings(environment)
    risks: Dict[str, str] = {}
    for pest, reqs in factors.items():
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
        risks[pest] = level
    return risks


def classify_pest_severity(
    plant_type: str, observations: Mapping[str, int]
) -> Dict[str, str]:
    """Return ``low``, ``moderate`` or ``severe`` for each observed pest.

    The classification uses :data:`pest_thresholds.json` values where counts
    below the threshold are ``"low"``, counts up to double the threshold are
    ``"moderate"`` and anything higher is ``"severe"``.
    """

    thresholds = get_pest_thresholds(plant_type)
    severity: Dict[str, str] = {}
    for pest, count in observations.items():
        key = normalize_key(pest)
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


@dataclass
class PestReport:
    """Consolidated pest monitoring report."""

    severity: Dict[str, str]
    thresholds_exceeded: Dict[str, bool]
    treatments: Dict[str, str]
    beneficial_insects: Dict[str, list[str]]
    prevention: Dict[str, str]
    severity_actions: Dict[str, str]

    def as_dict(self) -> Dict[str, object]:
        """Return report as a regular dictionary."""
        return asdict(self)


def generate_pest_report(
    plant_type: str, observations: Mapping[str, int]
) -> Dict[str, object]:
    """Return severity, treatment and prevention recommendations."""

    severity = classify_pest_severity(plant_type, observations)
    thresholds = assess_pest_pressure(plant_type, observations)
    treatments = recommend_threshold_actions(plant_type, observations)
    beneficials = recommend_biological_controls(plant_type, observations)

    from .pest_manager import recommend_prevention

    prevention = recommend_prevention(plant_type, observations.keys())

    severity_actions = {s: get_severity_action(lvl) for s, lvl in severity.items()}

    report = PestReport(
        severity=severity,
        thresholds_exceeded=thresholds,
        treatments=treatments,
        beneficial_insects=beneficials,
        prevention=prevention,
        severity_actions=severity_actions,
    )
    return report.as_dict()

