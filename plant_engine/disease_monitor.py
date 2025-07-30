"""Disease threshold monitoring utilities."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Dict, Mapping

from .utils import load_dataset, normalize_key, list_dataset_entries
from .monitor_utils import (
    get_interval as _get_interval,
    next_date as _next_date,
    generate_schedule as _generate_schedule,
    calculate_risk_score,
)
from .disease_manager import recommend_treatments, recommend_prevention
from . import disease_manager

DATA_FILE = "diseases/disease_thresholds.json"
MONITOR_INTERVAL_FILE = "diseases/disease_monitoring_intervals.json"
RISK_DATA_FILE = "diseases/disease_risk_factors.json"
SEVERITY_ACTIONS_FILE = "diseases/disease_severity_actions.json"
RISK_INTERVAL_MOD_FILE = "diseases/disease_risk_interval_modifiers.json"
SCOUTING_METHOD_FILE = "diseases/disease_scouting_methods.json"

# Cached dataset
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)
# Recommended days between scouting events per plant stage
_MONITOR_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(MONITOR_INTERVAL_FILE)
_RISK_FACTORS: Dict[str, Dict[str, Dict[str, list]]] = load_dataset(RISK_DATA_FILE)
_SEVERITY_ACTIONS: Dict[str, str] = load_dataset(SEVERITY_ACTIONS_FILE)
_RISK_MODIFIERS: Dict[str, float] = load_dataset(RISK_INTERVAL_MOD_FILE)
_SCOUTING_METHODS: Dict[str, str] = load_dataset(SCOUTING_METHOD_FILE)

__all__ = [
    "list_supported_plants",
    "get_disease_thresholds",
    "assess_disease_pressure",
    "classify_disease_severity",
    "recommend_threshold_actions",
    "get_severity_action",
    "estimate_disease_risk",
    "adjust_risk_with_resistance",
    "estimate_adjusted_disease_risk",
    "get_monitoring_interval",
    "risk_adjusted_monitor_interval",
    "next_monitor_date",
    "generate_monitoring_schedule",
    "generate_detailed_monitoring_schedule",
    "generate_disease_report",
    "DiseaseReport",
    "get_scouting_method",
    "summarize_disease_management",
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

    from .monitor_utils import estimate_condition_risk

    return estimate_condition_risk(factors, environment)


def adjust_risk_with_resistance(
    plant_type: str, risk_map: Mapping[str, str]
) -> Dict[str, str]:
    """Return ``risk_map`` adjusted by crop disease resistance ratings."""

    levels = ["low", "moderate", "high"]
    adjusted: Dict[str, str] = {}
    for disease, risk in risk_map.items():
        rating = disease_manager.get_disease_resistance(plant_type, disease)
        if rating is None or risk not in levels:
            adjusted[disease] = risk
            continue

        idx = levels.index(risk)
        if rating >= 4 and idx > 0:
            idx -= 1
        elif rating <= 2 and idx < len(levels) - 1:
            idx += 1
        adjusted[disease] = levels[idx]

    return adjusted


def estimate_adjusted_disease_risk(
    plant_type: str, environment: Mapping[str, float]
) -> Dict[str, str]:
    """Return environment-based disease risk adjusted for crop resistance."""

    risk = estimate_disease_risk(plant_type, environment)
    if not risk:
        return {}
    return adjust_risk_with_resistance(plant_type, risk)


def get_monitoring_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between disease scouting events."""

    return _get_interval(_MONITOR_INTERVALS, plant_type, stage)


def risk_adjusted_monitor_interval(
    plant_type: str,
    stage: str | None,
    environment: Mapping[str, float],
) -> int | None:
    """Return monitoring interval adjusted for current disease risk."""

    base = get_monitoring_interval(plant_type, stage)
    if base is None:
        return None

    risks = estimate_adjusted_disease_risk(plant_type, environment)
    level = "low"
    if any(r == "high" for r in risks.values()):
        level = "high"
    elif any(r == "moderate" for r in risks.values()):
        level = "moderate"

    modifier = _RISK_MODIFIERS.get(level, 1.0)
    interval = int(round(base * modifier))
    return max(1, interval)


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


def generate_detailed_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[dict[str, object]]:
    """Return monitoring dates with scouting methods for each disease."""

    dates = generate_monitoring_schedule(plant_type, stage, start, events)
    diseases = disease_manager.list_known_diseases(plant_type)
    methods = {d: get_scouting_method(d) for d in diseases}
    return [{"date": d, "methods": methods} for d in dates]


def get_severity_action(level: str) -> str:
    """Return recommended action for a severity ``level``."""

    return _SEVERITY_ACTIONS.get(level.lower(), "")


def get_scouting_method(disease: str) -> str:
    """Return recommended scouting approach for ``disease``."""

    return _SCOUTING_METHODS.get(normalize_key(disease), "")


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


def summarize_disease_management(
    plant_type: str,
    stage: str | None,
    observations: Mapping[str, int],
    environment: Mapping[str, float] | None = None,
    last_date: date | None = None,
) -> Dict[str, object]:
    """Return consolidated disease status and recommendations."""

    report = generate_disease_report(plant_type, observations)

    risk: Dict[str, str] | None = None
    risk_score: float | None = None
    next_date_val: date | None = None
    interval: int | None = None
    if environment is not None:
        risk = estimate_adjusted_disease_risk(plant_type, environment)
        risk_score = calculate_risk_score(risk)
        if last_date is not None:
            interval = risk_adjusted_monitor_interval(plant_type, stage, environment)
            if interval is not None:
                next_date_val = last_date + timedelta(days=interval)

    data = {**report, "risk": risk or {}}
    if risk_score is not None:
        data["risk_score"] = risk_score
    if interval is not None:
        data["monitor_interval_days"] = interval
    if next_date_val is not None:
        data["next_monitor_date"] = next_date_val
    return data
