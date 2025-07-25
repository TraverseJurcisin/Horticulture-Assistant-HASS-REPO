"""Pest monitoring utilities using threshold datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Dict, Mapping

from . import environment_manager

from .utils import load_dataset, normalize_key, list_dataset_entries
from .monitor_utils import get_interval as _get_interval, next_date as _next_date, generate_schedule as _generate_schedule
from .pest_manager import (
    recommend_treatments,
    recommend_beneficials,
    get_pest_resistance,
)

DATA_FILE = "pest_thresholds.json"
RISK_DATA_FILE = "pest_risk_factors.json"
SEVERITY_ACTIONS_FILE = "pest_severity_actions.json"
# Recommended days between scouting events
MONITOR_INTERVAL_FILE = "pest_monitoring_intervals.json"
# Adjustment factors for risk-based interval modifications
RISK_INTERVAL_MOD_FILE = "pest_risk_interval_modifiers.json"

# Load once with caching
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(DATA_FILE)
_RISK_FACTORS: Dict[str, Dict[str, Dict[str, list]]] = load_dataset(RISK_DATA_FILE)
_SEVERITY_ACTIONS: Dict[str, str] = load_dataset(SEVERITY_ACTIONS_FILE)
_MONITOR_INTERVALS: Dict[str, Dict[str, int]] = load_dataset(MONITOR_INTERVAL_FILE)
_RISK_MODIFIERS: Dict[str, float] = load_dataset(RISK_INTERVAL_MOD_FILE)

__all__ = [
    "list_supported_plants",
    "get_pest_thresholds",
    "assess_pest_pressure",
    "classify_pest_severity",
    "recommend_threshold_actions",
    "recommend_biological_controls",
    "estimate_pest_risk",
    "adjust_risk_with_resistance",
    "estimate_adjusted_pest_risk",
    "generate_pest_report",
    "get_severity_action",
    "get_monitoring_interval",
    "risk_adjusted_monitor_interval",
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

    return _get_interval(_MONITOR_INTERVALS, plant_type, stage)


def risk_adjusted_monitor_interval(
    plant_type: str,
    stage: str | None,
    environment: Mapping[str, float],
) -> int | None:
    """Return monitoring interval adjusted for current pest risk."""

    base = get_monitoring_interval(plant_type, stage)
    if base is None:
        return None

    risks = estimate_pest_risk(plant_type, environment)
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
    """Return the next pest scouting date based on interval guidelines."""

    return _next_date(_MONITOR_INTERVALS, plant_type, stage, last_date)


def generate_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[date]:
    """Return list of upcoming monitoring dates."""

    return _generate_schedule(_MONITOR_INTERVALS, plant_type, stage, start, events)


def get_severity_action(level: str) -> str:
    """Return recommended action for a severity ``level``."""

    return _SEVERITY_ACTIONS.get(level.lower(), "")


def assess_pest_pressure(plant_type: str, observations: Mapping[str, int]) -> Dict[str, bool]:
    """Return mapping of pests to ``True`` if threshold exceeded."""

    thresholds = get_pest_thresholds(plant_type)
    pressure: Dict[str, bool] = {}
    for pest, count in observations.items():
        if count < 0:
            raise ValueError("pest counts must be non-negative")
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

    from .monitor_utils import estimate_condition_risk

    return estimate_condition_risk(factors, environment)


def adjust_risk_with_resistance(
    plant_type: str, risk_map: Mapping[str, str]
) -> Dict[str, str]:
    """Return ``risk_map`` adjusted by pest resistance ratings."""

    levels = ["low", "moderate", "high"]
    adjusted: Dict[str, str] = {}
    for pest, risk in risk_map.items():
        rating = get_pest_resistance(plant_type, pest)
        if rating is None or risk not in levels:
            adjusted[pest] = risk
            continue

        idx = levels.index(risk)
        if rating >= 4 and idx > 0:
            idx -= 1
        elif rating <= 2 and idx < len(levels) - 1:
            idx += 1
        adjusted[pest] = levels[idx]

    return adjusted


def estimate_adjusted_pest_risk(
    plant_type: str, environment: Mapping[str, float]
) -> Dict[str, str]:
    """Return environment-based pest risk adjusted for crop resistance."""

    risk = estimate_pest_risk(plant_type, environment)
    if not risk:
        return {}
    return adjust_risk_with_resistance(plant_type, risk)


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
        if count < 0:
            raise ValueError("pest counts must be non-negative")
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


@dataclass(slots=True)
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

