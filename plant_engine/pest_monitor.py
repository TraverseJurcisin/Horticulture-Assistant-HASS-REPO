"""Pest monitoring utilities using threshold datasets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict, Mapping, Iterable


from .utils import lazy_dataset, normalize_key, list_dataset_entries
from .monitor_utils import (
    get_interval as _get_interval,
    next_date as _next_date,
    generate_schedule as _generate_schedule,
    calculate_risk_score,
)
from .pest_manager import (
    recommend_treatments,
    recommend_beneficials,
    get_pest_resistance,
    list_known_pests,
)

DATA_FILE = "pest_thresholds.json"
STAGE_DATA_FILE = "pest_thresholds_by_stage.json"
RISK_DATA_FILE = "pest_risk_factors.json"
SEVERITY_ACTIONS_FILE = "pest_severity_actions.json"
# Recommended days between scouting events
MONITOR_INTERVAL_FILE = "pest_monitoring_intervals.json"
# Adjustment factors for risk-based interval modifications
RISK_INTERVAL_MOD_FILE = "pest_risk_interval_modifiers.json"
SCOUTING_METHOD_FILE = "pest_scouting_methods.json"
SEVERITY_THRESHOLD_FILE = "pest_severity_thresholds.json"
SEVERITY_SCORE_FILE = "pest_severity_scores.json"
SAMPLE_SIZE_FILE = "pest_sample_sizes.json"
YIELD_LOSS_FILE = "pest_yield_loss.json"

# Load once with caching
_THRESHOLDS = lazy_dataset(DATA_FILE)
_STAGE_THRESHOLDS = lazy_dataset(STAGE_DATA_FILE)
_RISK_FACTORS = lazy_dataset(RISK_DATA_FILE)
_SEVERITY_ACTIONS = lazy_dataset(SEVERITY_ACTIONS_FILE)
_SEVERITY_THRESHOLDS = lazy_dataset(SEVERITY_THRESHOLD_FILE)
_SEVERITY_SCORES = lazy_dataset(SEVERITY_SCORE_FILE)
PRESSURE_WEIGHT_FILE = "pest_pressure_weights.json"
_PRESSURE_WEIGHTS = lazy_dataset(PRESSURE_WEIGHT_FILE)
_SAMPLE_SIZES = lazy_dataset(SAMPLE_SIZE_FILE)
_YIELD_LOSS = lazy_dataset(YIELD_LOSS_FILE)


def _resolve(data):
    """Return dataset contents from a mapping or callable loader."""

    return data() if callable(data) else data
_MONITOR_INTERVALS = lazy_dataset(MONITOR_INTERVAL_FILE)
_RISK_MODIFIERS = lazy_dataset(RISK_INTERVAL_MOD_FILE)
_SCOUTING_METHODS = lazy_dataset(SCOUTING_METHOD_FILE)

__all__ = [
    "list_supported_plants",
    "get_pest_thresholds",
    "get_pest_threshold",
    "is_threshold_exceeded",
    "assess_pest_pressure",
    "calculate_pest_pressure_index",
    "classify_pest_severity",
    "recommend_threshold_actions",
    "recommend_biological_controls",
    "estimate_pest_risk",
    "adjust_risk_with_resistance",
    "estimate_adjusted_pest_risk",
    "estimate_adjusted_pest_risk_series",
    "generate_pest_report",
    "calculate_severity_index",
    "get_scouting_method",
    "get_severity_action",
    "get_severity_thresholds",
    "calculate_pest_management_index",
    "calculate_pest_management_index_series",
    "get_monitoring_interval",
    "risk_adjusted_monitor_interval",
    "next_monitor_date",
    "generate_monitoring_schedule",
    "generate_detailed_monitoring_schedule",
    "get_sample_size",
    "estimate_yield_loss",
    "PestReport",
    "summarize_pest_management",
]


def get_pest_thresholds(plant_type: str, stage: str | None = None) -> Dict[str, int]:
    """Return pest count thresholds for ``plant_type`` and optional ``stage``.

    Lookup is case-insensitive and spaces are ignored so ``"Citrus"`` and
    ``"citrus"`` map to the same dataset entry. Stage-specific thresholds are
    loaded from :data:`pest_thresholds_by_stage.json` when available and fall
    back to base values from :data:`pest_thresholds.json`.
    """

    key = normalize_key(plant_type)
    base = _resolve(_THRESHOLDS).get(key, {})

    if stage:
        stage_data = _resolve(_STAGE_THRESHOLDS).get(key, {})
        thresh = stage_data.get(normalize_key(stage))
        if isinstance(thresh, Mapping):
            # merge with base thresholds so partial definitions inherit defaults
            merged = dict(base)
            merged.update(thresh)
            return merged

    return base


def get_pest_threshold(plant_type: str, pest: str) -> int | None:
    """Return the threshold count for ``pest`` on ``plant_type`` if defined."""

    data = get_pest_thresholds(plant_type)
    value = data.get(normalize_key(pest))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def is_threshold_exceeded(plant_type: str, pest: str, count: int) -> bool | None:
    """Return ``True`` if ``count`` meets or exceeds the action threshold."""

    if count < 0:
        raise ValueError("count must be non-negative")
    thresh = get_pest_threshold(plant_type, pest)
    if thresh is None:
        return None
    return count >= thresh


def list_supported_plants() -> list[str]:
    """Return plant types with pest threshold definitions."""

    union = set(list_dataset_entries(_resolve(_THRESHOLDS)))
    union.update(list_dataset_entries(_resolve(_STAGE_THRESHOLDS)))
    return sorted(union)


def get_monitoring_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return recommended days between scouting events for a plant stage."""

    return _get_interval(_resolve(_MONITOR_INTERVALS), plant_type, stage)


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

    modifiers = _resolve(_RISK_MODIFIERS)
    modifier = modifiers.get(level, 1.0)
    interval = int(round(base * modifier))
    return max(1, interval)


def next_monitor_date(
    plant_type: str, stage: str | None, last_date: date
) -> date | None:
    """Return the next pest scouting date based on interval guidelines."""

    return _next_date(_resolve(_MONITOR_INTERVALS), plant_type, stage, last_date)


def generate_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[date]:
    """Return list of upcoming monitoring dates."""

    return _generate_schedule(_resolve(_MONITOR_INTERVALS), plant_type, stage, start, events)


def generate_detailed_monitoring_schedule(
    plant_type: str,
    stage: str | None,
    start: date,
    events: int,
) -> list[dict[str, object]]:
    """Return monitoring dates with scouting methods for each pest."""

    dates = generate_monitoring_schedule(plant_type, stage, start, events)
    pests = list_known_pests(plant_type)
    methods = {p: get_scouting_method(p) for p in pests}
    return [{"date": d, "methods": methods} for d in dates]


def get_severity_action(level: str) -> str:
    """Return recommended action for a severity ``level``."""

    actions = _resolve(_SEVERITY_ACTIONS)
    return actions.get(level.lower(), "")


def get_scouting_method(pest: str) -> str:
    """Return recommended scouting approach for ``pest``."""

    methods = _resolve(_SCOUTING_METHODS)
    return methods.get(normalize_key(pest), "")


def get_severity_thresholds(pest: str) -> Dict[str, float]:
    """Return population thresholds for severity levels of ``pest``."""

    thresholds = _resolve(_SEVERITY_THRESHOLDS)
    return thresholds.get(normalize_key(pest), {})


def get_sample_size(plant_type: str) -> int | None:
    """Return recommended sample size for ``plant_type`` pest scouting."""

    sizes = _resolve(_SAMPLE_SIZES)
    value = sizes.get(normalize_key(plant_type)) if isinstance(sizes, Mapping) else None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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


def calculate_pest_pressure_index(plant_type: str, observations: Mapping[str, int]) -> float:
    """Return 0-100 index of overall pest pressure severity."""

    thresholds = get_pest_thresholds(plant_type)
    if not thresholds:
        return 0.0

    total = 0.0
    count = 0
    for pest, limit in thresholds.items():
        observed = float(observations.get(pest, 0))
        try:
            limit_val = float(limit)
        except (TypeError, ValueError):
            continue
        if limit_val <= 0:
            continue
        ratio = min(observed / limit_val, 1.0)
        total += ratio
        count += 1

    if count == 0:
        return 0.0

    return round((total / count) * 100, 1)


def calculate_severity_index(severity_map: Mapping[str, str]) -> float:
    """Return average numeric score for a pest severity mapping."""

    if not severity_map:
        return 0.0

    scores = _SEVERITY_SCORES()
    total = 0.0
    count = 0
    for level in severity_map.values():
        try:
            total += float(scores.get(level, 0))
            count += 1
        except (TypeError, ValueError):
            continue
    return round(total / count, 2) if count else 0.0


def estimate_yield_loss(severity_map: Mapping[str, str]) -> float:
    """Return estimated percent yield loss based on pest severity levels."""

    if not severity_map:
        return 0.0

    data = _resolve(_YIELD_LOSS)
    total = 0.0
    for pest, level in severity_map.items():
        info = data.get(normalize_key(pest))
        if not isinstance(info, Mapping):
            continue
        try:
            loss = float(info.get(level, 0))
        except (TypeError, ValueError):
            loss = 0.0
        total += loss
    return round(min(total, 100.0), 2)


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

    factors = _resolve(_RISK_FACTORS).get(normalize_key(plant_type), {})
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


def estimate_adjusted_pest_risk_series(
    plant_type: str, series: Iterable[Mapping[str, float]]
) -> Dict[str, str]:
    """Return combined pest risk across multiple environment readings."""

    levels = {"low": 1, "moderate": 2, "high": 3}
    combined: Dict[str, int] = {}
    for env in series:
        risk = estimate_adjusted_pest_risk(plant_type, env)
        for pest, level in risk.items():
            rank = levels.get(level, 0)
            if rank > combined.get(pest, 0):
                combined[pest] = rank

    inv_levels = {v: k for k, v in levels.items()}
    return {p: inv_levels[r] for p, r in combined.items()}


def calculate_pest_management_index(
    plant_type: str,
    observations: Mapping[str, int],
    environment: Mapping[str, float] | None = None,
) -> float:
    """Return 0-100 index combining pressure and environmental risk."""

    pressure = calculate_pest_pressure_index(plant_type, observations)
    if environment is None:
        return pressure

    risk = estimate_adjusted_pest_risk(plant_type, environment)
    if not risk:
        return pressure
    risk_score = calculate_risk_score(risk)
    risk_index = (risk_score / 3.0) * 100 if risk_score else 0.0

    weights = _PRESSURE_WEIGHTS() or {}
    p_w = float(weights.get("pressure", 1.0))
    r_w = float(weights.get("risk", 1.0))
    total = p_w + r_w
    if total <= 0:
        return 0.0
    return round((pressure * p_w + risk_index * r_w) / total, 1)


def calculate_pest_management_index_series(
    plant_type: str,
    series: Iterable[Mapping[str, int]],
    *,
    env_series: Iterable[Mapping[str, float]] | None = None,
) -> float:
    """Return average pest management index across multiple observations.

    ``series`` provides successive pest observations. When ``env_series`` is
    supplied, each observation is paired with the corresponding environment
    readings. Extra observations without a matching environment map are
    evaluated using pressure only. Missing observations yield ``0.0``.
    """

    total = 0.0
    count = 0

    if env_series is None:
        for obs in series:
            total += calculate_pest_management_index(plant_type, obs)
            count += 1
    else:
        for obs, env in zip(series, env_series):
            total += calculate_pest_management_index(plant_type, obs, env)
            count += 1

    return round(total / count, 1) if count else 0.0


def classify_pest_severity(
    plant_type: str, observations: Mapping[str, int]
) -> Dict[str, str]:
    """Return ``low``, ``moderate`` or ``severe`` for each observed pest.

    Severity levels are determined using optional values from
    :data:`pest_severity_thresholds.json`. When no custom thresholds are
    defined, the base values from :data:`pest_thresholds.json` are used and a
    simple doubling rule defines the ``severe`` boundary.
    """

    thresholds = get_pest_thresholds(plant_type)
    severity: Dict[str, str] = {}
    for pest, count in observations.items():
        if count < 0:
            raise ValueError("pest counts must be non-negative")
        key = normalize_key(pest)
        base = thresholds.get(key)
        if base is None:
            continue

        custom = get_severity_thresholds(key)
        moderate = custom.get("moderate", base)
        severe = custom.get("severe")
        if severe is None:
            severe = moderate * 2 if moderate is not None else None

        if severe is not None and count >= severe:
            level = "severe"
        elif count >= moderate:
            level = "moderate"
        else:
            level = "low"
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
    severity_index: float
    yield_loss: float

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
    index = calculate_severity_index(severity)
    yield_loss = estimate_yield_loss(severity)

    report = PestReport(
        severity=severity,
        thresholds_exceeded=thresholds,
        treatments=treatments,
        beneficial_insects=beneficials,
        prevention=prevention,
        severity_actions=severity_actions,
        severity_index=index,
        yield_loss=yield_loss,
    )
    return report.as_dict()


def summarize_pest_management(
    plant_type: str,
    stage: str | None,
    observations: Mapping[str, int],
    environment: Mapping[str, float] | None = None,
    last_date: date | None = None,
) -> Dict[str, object]:
    """Return consolidated pest status and recommendations.

    Parameters
    ----------
    plant_type : str
        Crop identifier for dataset lookup.
    stage : str, optional
        Growth stage for monitoring interval calculations.
    observations : Mapping[str, int]
        Current pest counts from scouting observations.
    environment : Mapping[str, float], optional
        Environmental readings used to estimate pest risk.
    last_date : date, optional
        Date of the previous scouting event for scheduling the next one.
    """

    report = generate_pest_report(plant_type, observations)

    risk: Dict[str, str] | None = None
    risk_score: float | None = None
    next_date_val: date | None = None
    interval: int | None = None
    if environment is not None:
        risk = estimate_adjusted_pest_risk(plant_type, environment)
        risk_score = calculate_risk_score(risk)
        if last_date is not None:
            interval = risk_adjusted_monitor_interval(
                plant_type, stage, environment
            )
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

