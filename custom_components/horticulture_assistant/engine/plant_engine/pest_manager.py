"""Pest management guideline utilities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

from .growth_stage import generate_stage_schedule
from .utils import (list_dataset_entries, load_dataset, normalize_key,
                    stage_value)

DATA_FILE = "pests/pest_guidelines.json"
BENEFICIAL_FILE = "pests/beneficial_insects.json"
PREVENTION_FILE = "pests/pest_prevention.json"
IPM_FILE = "pests/ipm_guidelines.json"
RESISTANCE_FILE = "pests/pest_resistance_ratings.json"
ORGANIC_FILE = "pests/organic_pest_controls.json"
TAXONOMY_FILE = "pests/pest_scientific_names.json"
COMMON_NAME_FILE = "pests/pest_common_names.json"
RELEASE_RATE_FILE = "pests/beneficial_release_rates.json"
LIFECYCLE_FILE = "pests/pest_lifecycle_durations.json"
MONITOR_FILE = "pests/pest_monitoring_intervals.json"
THRESHOLD_FILE = "pests/pest_thresholds.json"
STAGE_THRESHOLD_FILE = "pests/pest_thresholds_by_stage.json"
RISK_MOD_FILE = "pests/pest_risk_interval_modifiers.json"
SCOUTING_FILE = "pests/pest_scouting_methods.json"
EFFECTIVE_FILE = "pests/beneficial_effective_days.json"
SEVERITY_THRESHOLDS_FILE = "pests/pest_severity_thresholds.json"
SEVERITY_SCORES_FILE = "pests/pest_severity_scores.json"
SEVERITY_ACTIONS_FILE = "pests/pest_severity_actions.json"


# Datasets are cached by ``load_dataset`` so loaded once at import time
_DATA: dict[str, dict[str, str]] = load_dataset(DATA_FILE)
_BENEFICIALS: dict[str, list[str]] = load_dataset(BENEFICIAL_FILE)
_RELEASE_RATES: dict[str, float] = load_dataset(RELEASE_RATE_FILE)
_PREVENTION: dict[str, dict[str, str]] = load_dataset(PREVENTION_FILE)
_IPM: dict[str, dict[str, str]] = load_dataset(IPM_FILE)
_RESISTANCE: dict[str, dict[str, float]] = load_dataset(RESISTANCE_FILE)
_ORGANIC: dict[str, list[str]] = load_dataset(ORGANIC_FILE)
_TAXONOMY: dict[str, str] = load_dataset(TAXONOMY_FILE)
_COMMON_NAMES: dict[str, str] = load_dataset(COMMON_NAME_FILE)
_LIFECYCLE: dict[str, dict[str, int]] = load_dataset(LIFECYCLE_FILE)
_MONITORING: dict[str, dict[str, int]] = load_dataset(MONITOR_FILE)
_THRESHOLDS: dict[str, dict[str, int]] = load_dataset(THRESHOLD_FILE)
_STAGE_THRESHOLDS: dict[str, dict[str, dict[str, int]]] = load_dataset(STAGE_THRESHOLD_FILE)
_RISK_MODIFIERS: dict[str, float] = load_dataset(RISK_MOD_FILE)
_SCOUT_METHODS: dict[str, str] = load_dataset(SCOUTING_FILE)
_EFFECTIVE_DAYS: dict[str, int] = load_dataset(EFFECTIVE_FILE)
_RAW_THRESHOLDS: dict[str, dict[str, int]] = load_dataset(SEVERITY_THRESHOLDS_FILE)
_SEVERITY_THRESHOLDS: dict[str, dict[str, int]] = {
    normalize_key(k): v for k, v in _RAW_THRESHOLDS.items()
}
_SEVERITY_SCORES: dict[str, float] = load_dataset(SEVERITY_SCORES_FILE)
_SEVERITY_ACTIONS: dict[str, str] = load_dataset(SEVERITY_ACTIONS_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with pest guidelines."""
    return list_dataset_entries(_DATA)


def get_pest_guidelines(plant_type: str) -> dict[str, str]:
    """Return pest management guidelines for the specified plant type."""
    return _DATA.get(normalize_key(plant_type), {})


def list_known_pests(plant_type: str) -> list[str]:
    """Return all pests with guidelines for ``plant_type``."""
    return sorted(get_pest_guidelines(plant_type).keys())


def list_supported_pests() -> list[str]:
    """Return unique pest names available across all crops."""

    pests: set[str] = set()
    for guidelines in _DATA.values():
        pests.update(guidelines.keys())
    return sorted(pests)


def get_scientific_name(pest: str) -> str | None:
    """Return the scientific (Latin) name for ``pest`` if known."""
    return _TAXONOMY.get(normalize_key(pest))


def get_common_name(scientific_name: str) -> str | None:
    """Return the common name for a scientific pest identifier."""
    return _COMMON_NAMES.get(scientific_name)


def get_pest_resistance(plant_type: str, pest: str) -> float | None:
    """Return relative resistance rating of a plant to ``pest``.

    Ratings are arbitrary scores (1-5) where higher values indicate
    greater natural resistance. ``None`` is returned when no rating is
    defined for the plant/pest combination.
    """

    data = _RESISTANCE.get(normalize_key(plant_type), {})
    value = data.get(normalize_key(pest))
    return float(value) if isinstance(value, int | float) else None


def get_severity_thresholds(pest: str | None = None) -> dict[str, int]:
    """Return severity thresholds for ``pest`` or the default scale."""

    key = normalize_key(pest) if pest else "scale"
    data = _SEVERITY_THRESHOLDS.get(key)
    if not isinstance(data, Mapping):
        data = _SEVERITY_THRESHOLDS.get("scale", {})
    result: dict[str, int] = {}
    for k in ("moderate", "severe"):
        v = data.get(k)
        if isinstance(v, int | float):
            result[k] = int(v)
    return result


def classify_pest_severity(count: int, pest: str | None = None) -> str:
    """Return ``low``, ``moderate`` or ``severe`` based on ``count``."""

    thresholds = get_severity_thresholds(pest)
    moderate = thresholds.get("moderate", float("inf"))
    severe = thresholds.get("severe", float("inf"))
    if count >= severe:
        return "severe"
    if count >= moderate:
        return "moderate"
    return "low"


def assess_pest_severity(counts: Mapping[str, int]) -> dict[str, str]:
    """Return severity classification for each pest count entry."""

    return {p: classify_pest_severity(int(c), p) for p, c in counts.items()}


def calculate_severity_index(severity_map: Mapping[str, str]) -> float:
    """Return average numeric severity score for ``severity_map``."""

    if not severity_map:
        return 0.0

    total = 0.0
    count = 0
    for level in severity_map.values():
        try:
            total += float(_SEVERITY_SCORES.get(level, 0))
            count += 1
        except (TypeError, ValueError):
            continue
    return total / count if count else 0.0


def recommend_severity_actions(counts: Mapping[str, int]) -> dict[str, str]:
    """Return actions based on assessed pest population severity."""

    severity = assess_pest_severity(counts)
    actions: dict[str, str] = {}
    for pest, level in severity.items():
        actions[pest] = _SEVERITY_ACTIONS.get(level, "")
    return actions


def recommend_treatments(plant_type: str, pests: Iterable[str]) -> dict[str, str]:
    """Return recommended treatment strings for each observed pest."""
    guide = get_pest_guidelines(plant_type)
    actions: dict[str, str] = {}
    for pest in pests:
        actions[pest] = guide.get(pest, "No guideline available")
    return actions


def get_beneficial_insects(pest: str) -> list[str]:
    """Return a list of beneficial insects that prey on ``pest``."""
    return _BENEFICIALS.get(pest.lower(), [])


def recommend_beneficials(pests: Iterable[str]) -> dict[str, list[str]]:
    """Return beneficial insect suggestions for observed ``pests``."""
    return {p: get_beneficial_insects(p) for p in pests}


def get_beneficial_release_rate(insect: str) -> float | None:
    """Return recommended release rate for a beneficial insect per m²."""

    rate = _RELEASE_RATES.get(normalize_key(insect))
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):
        return None


def recommend_release_rates(pests: Iterable[str]) -> dict[str, dict[str, float]]:
    """Return release rates for beneficials targeting the given pests."""

    rec: dict[str, dict[str, float]] = {}
    for pest in pests:
        insects = get_beneficial_insects(pest)
        rates: dict[str, float] = {}
        for insect in insects:
            rate = get_beneficial_release_rate(insect)
            if rate is not None:
                rates[insect] = rate
        if rates:
            rec[pest] = rates
    return rec


def get_beneficial_effective_days(insect: str) -> int | None:
    """Return expected effective duration in days for a beneficial insect."""

    days = _EFFECTIVE_DAYS.get(normalize_key(insect))
    try:
        return int(days) if days is not None else None
    except (TypeError, ValueError):
        return None


def plan_beneficial_releases(
    pests: Iterable[str], start: date, cycles: int = 3
) -> list[dict[str, object]]:
    """Return recurring beneficial insect release schedule."""

    insects: set[str] = set()
    for pest in pests:
        insects.update(get_beneficial_insects(pest))
    if not insects:
        return []

    # Default to weekly releases if no data available
    interval = min(
        (get_beneficial_effective_days(i) or 7 for i in insects),
        default=7,
    )

    schedule: list[dict[str, object]] = []
    for idx in range(cycles):
        releases = {insect: get_beneficial_release_rate(insect) or 0.0 for insect in insects}
        schedule.append({"date": start + timedelta(days=idx * interval), "releases": releases})

    return schedule


def get_organic_controls(pest: str) -> list[str]:
    """Return organic control options for ``pest``."""

    return _ORGANIC.get(normalize_key(pest), [])


def recommend_organic_controls(pests: Iterable[str]) -> dict[str, list[str]]:
    """Return organic control recommendations for observed ``pests``."""

    return {p: get_organic_controls(p) for p in pests}


def get_pest_lifecycle(pest: str) -> dict[str, int]:
    """Return lifecycle stage durations in days for ``pest``."""

    data = _LIFECYCLE.get(normalize_key(pest))
    if not isinstance(data, Mapping):
        return {}
    result: dict[str, int] = {}
    for stage, days in data.items():
        try:
            result[stage] = int(days)
        except (TypeError, ValueError):
            continue
    return result


def get_monitoring_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return scouting interval in days for a plant stage."""

    value = stage_value(_MONITORING, plant_type, stage)
    return int(value) if isinstance(value, int | float) else None


def get_pest_threshold(plant_type: str, pest: str, stage: str | None = None) -> int | None:
    """Return pest count threshold triggering action."""

    if stage:
        crop = _STAGE_THRESHOLDS.get(normalize_key(plant_type), {})
        stage_data = crop.get(normalize_key(stage))
        if isinstance(stage_data, Mapping):
            value = stage_data.get(normalize_key(pest))
            if isinstance(value, int | float):
                return int(value)

    crop = _THRESHOLDS.get(normalize_key(plant_type), {})
    value = crop.get(normalize_key(pest))
    return int(value) if isinstance(value, int | float) else None


def get_scouting_method(pest: str) -> str | None:
    """Return recommended scouting method for ``pest``."""

    return _SCOUT_METHODS.get(normalize_key(pest))


def recommend_monitoring_interval(
    plant_type: str,
    stage: str | None = None,
    risk_level: str | None = None,
) -> int | None:
    """Return scouting interval adjusted for risk level."""

    base = get_monitoring_interval(plant_type, stage)
    if base is None:
        return None
    if risk_level:
        factor = _RISK_MODIFIERS.get(normalize_key(risk_level))
        if isinstance(factor, int | float) and factor > 0:
            base = round(base * float(factor))
    return int(base)


def build_monitoring_plan(
    plant_type: str,
    pests: Iterable[str],
    stage: str | None = None,
    risk_level: str | None = None,
) -> dict[str, Any]:
    """Return monitoring interval, thresholds and methods for ``pests``."""

    interval = recommend_monitoring_interval(plant_type, stage, risk_level)
    thresholds: dict[str, int] = {}
    methods: dict[str, str] = {}
    for p in pests:
        thresh = get_pest_threshold(plant_type, p, stage)
        if thresh is not None:
            thresholds[p] = thresh
        methods[p] = get_scouting_method(p) or "Visual inspection"

    return {
        "interval_days": interval,
        "thresholds": thresholds,
        "methods": methods,
    }


def get_pest_prevention(plant_type: str) -> dict[str, str]:
    """Return pest prevention guidelines for ``plant_type``."""
    return _PREVENTION.get(normalize_key(plant_type), {})


def recommend_prevention(plant_type: str, pests: Iterable[str]) -> dict[str, str]:
    """Return preventative actions for each observed pest."""
    guide = get_pest_prevention(plant_type)
    actions: dict[str, str] = {}
    for pest in pests:
        actions[pest] = guide.get(pest, "No guideline available")
    return actions


def get_ipm_guidelines(plant_type: str) -> dict[str, str]:
    """Return integrated pest management guidance for a crop."""
    return _IPM.get(normalize_key(plant_type), {})


def recommend_ipm_actions(plant_type: str, pests: Iterable[str] | None = None) -> dict[str, str]:
    """Return IPM actions for the crop and specific pests if provided."""
    data = get_ipm_guidelines(plant_type)
    if not data:
        return {}
    actions: dict[str, str] = {}
    general = data.get("general")
    if general:
        actions["general"] = general
    if pests:
        for pest in pests:
            action = data.get(normalize_key(pest))
            if action:
                actions[pest] = action
    return actions


def build_pest_management_plan(plant_type: str, pests: Iterable[str]) -> dict[str, Any]:
    """Return a consolidated IPM plan for ``plant_type`` and ``pests``.

    The returned mapping contains a ``"general"`` entry when overall IPM
    guidance is available. Each pest key maps to a dictionary with keys
    ``treatment``, ``prevention``, ``beneficials`` and ``ipm``.
    """

    pest_list = [normalize_key(p) for p in pests]

    plan: dict[str, Any] = {}

    # IPM actions may include a general recommendation in addition to per pest
    ipm_actions = recommend_ipm_actions(plant_type, pest_list)
    general = ipm_actions.pop("general", None)
    if general:
        plan["general"] = general

    treatments = recommend_treatments(plant_type, pest_list)
    prevention = recommend_prevention(plant_type, pest_list)
    beneficials = recommend_beneficials(pest_list)
    organic = recommend_organic_controls(pest_list)

    for pest in pest_list:
        sci = get_scientific_name(pest)
        common = get_common_name(sci) if sci else get_common_name(pest)
        if common is None:
            common = pest
        plan[pest] = {
            "treatment": treatments.get(pest, "No guideline available"),
            "prevention": prevention.get(pest, "No guideline available"),
            "beneficials": beneficials.get(pest, []),
            "ipm": ipm_actions.get(pest),
            "organic": organic.get(pest, []),
            "scientific_name": sci,
            "common_name": common,
            "lifecycle": get_pest_lifecycle(pest),
        }

    return plan


def generate_cycle_monitoring_schedule(
    plant_type: str,
    start_date: date,
    pests: Iterable[str],
    *,
    risk_level: str | None = None,
) -> list[dict[str, object]]:
    """Return list of monitoring tasks for the crop cycle.

    Each entry contains ``date``, ``stage`` and a ``plan`` dictionary from
    :func:`build_monitoring_plan`. The schedule is derived from growth stage
    durations and stage-specific monitoring intervals.
    """

    stage_schedule = generate_stage_schedule(plant_type, start_date)
    if not stage_schedule:
        return []

    tasks: list[dict[str, object]] = []
    for stage_info in stage_schedule:
        stage = stage_info["stage"]
        interval = get_monitoring_interval(plant_type, stage)
        if interval is None or interval <= 0:
            continue
        current = stage_info["start_date"] + timedelta(days=interval)
        end_date = stage_info["end_date"]
        while current <= end_date:
            tasks.append(
                {
                    "date": current,
                    "stage": stage,
                    "plan": build_monitoring_plan(plant_type, pests, stage, risk_level=risk_level),
                }
            )
            current += timedelta(days=interval)

    return tasks


__all__ = [
    "list_supported_plants",
    "get_pest_guidelines",
    "list_known_pests",
    "list_supported_pests",
    "get_scientific_name",
    "get_common_name",
    "recommend_treatments",
    "get_beneficial_insects",
    "recommend_beneficials",
    "get_beneficial_release_rate",
    "recommend_release_rates",
    "get_beneficial_effective_days",
    "plan_beneficial_releases",
    "get_organic_controls",
    "recommend_organic_controls",
    "get_pest_lifecycle",
    "get_severity_thresholds",
    "classify_pest_severity",
    "assess_pest_severity",
    "calculate_severity_index",
    "recommend_severity_actions",
    "get_monitoring_interval",
    "get_pest_threshold",
    "get_scouting_method",
    "recommend_monitoring_interval",
    "build_monitoring_plan",
    "get_pest_prevention",
    "recommend_prevention",
    "get_ipm_guidelines",
    "recommend_ipm_actions",
    "get_pest_resistance",
    "build_pest_management_plan",
    "generate_cycle_monitoring_schedule",
]
