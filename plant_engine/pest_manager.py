"""Pest management guideline utilities."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .utils import (
    load_dataset,
    normalize_key,
    list_dataset_entries,
    stage_value,
)

DATA_FILE = "pest_guidelines.json"
BENEFICIAL_FILE = "beneficial_insects.json"
PREVENTION_FILE = "pest_prevention.json"
IPM_FILE = "ipm_guidelines.json"
RESISTANCE_FILE = "pest_resistance_ratings.json"
ORGANIC_FILE = "organic_pest_controls.json"
TAXONOMY_FILE = "pest_scientific_names.json"
RELEASE_RATE_FILE = "beneficial_release_rates.json"
LIFECYCLE_FILE = "pest_lifecycle_durations.json"
MONITOR_FILE = "pest_monitoring_intervals.json"
THRESHOLD_FILE = "pest_thresholds.json"
STAGE_THRESHOLD_FILE = "pest_thresholds_by_stage.json"
RISK_MOD_FILE = "pest_risk_interval_modifiers.json"
SCOUTING_FILE = "pest_scouting_methods.json"



# Datasets are cached by ``load_dataset`` so loaded once at import time
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)
_BENEFICIALS: Dict[str, List[str]] = load_dataset(BENEFICIAL_FILE)
_RELEASE_RATES: Dict[str, float] = load_dataset(RELEASE_RATE_FILE)
_PREVENTION: Dict[str, Dict[str, str]] = load_dataset(PREVENTION_FILE)
_IPM: Dict[str, Dict[str, str]] = load_dataset(IPM_FILE)
_RESISTANCE: Dict[str, Dict[str, float]] = load_dataset(RESISTANCE_FILE)
_ORGANIC: Dict[str, List[str]] = load_dataset(ORGANIC_FILE)
_TAXONOMY: Dict[str, str] = load_dataset(TAXONOMY_FILE)
_LIFECYCLE: Dict[str, Dict[str, int]] = load_dataset(LIFECYCLE_FILE)
_MONITORING: Dict[str, Dict[str, int]] = load_dataset(MONITOR_FILE)
_THRESHOLDS: Dict[str, Dict[str, int]] = load_dataset(THRESHOLD_FILE)
_STAGE_THRESHOLDS: Dict[str, Dict[str, Dict[str, int]]] = load_dataset(
    STAGE_THRESHOLD_FILE
)
_RISK_MODIFIERS: Dict[str, float] = load_dataset(RISK_MOD_FILE)
_SCOUT_METHODS: Dict[str, str] = load_dataset(SCOUTING_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with pest guidelines."""
    return list_dataset_entries(_DATA)


def get_pest_guidelines(plant_type: str) -> Dict[str, str]:
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


def get_pest_resistance(plant_type: str, pest: str) -> float | None:
    """Return relative resistance rating of a plant to ``pest``.

    Ratings are arbitrary scores (1-5) where higher values indicate
    greater natural resistance. ``None`` is returned when no rating is
    defined for the plant/pest combination.
    """

    data = _RESISTANCE.get(normalize_key(plant_type), {})
    value = data.get(normalize_key(pest))
    return float(value) if isinstance(value, (int, float)) else None


def recommend_treatments(plant_type: str, pests: Iterable[str]) -> Dict[str, str]:
    """Return recommended treatment strings for each observed pest."""
    guide = get_pest_guidelines(plant_type)
    actions: Dict[str, str] = {}
    for pest in pests:
        actions[pest] = guide.get(pest, "No guideline available")
    return actions


def get_beneficial_insects(pest: str) -> List[str]:
    """Return a list of beneficial insects that prey on ``pest``."""
    return _BENEFICIALS.get(pest.lower(), [])


def recommend_beneficials(pests: Iterable[str]) -> Dict[str, List[str]]:
    """Return beneficial insect suggestions for observed ``pests``."""
    return {p: get_beneficial_insects(p) for p in pests}


def get_beneficial_release_rate(insect: str) -> float | None:
    """Return recommended release rate for a beneficial insect per m²."""

    rate = _RELEASE_RATES.get(normalize_key(insect))
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):
        return None


def recommend_release_rates(pests: Iterable[str]) -> Dict[str, Dict[str, float]]:
    """Return release rates for beneficials targeting the given pests."""

    rec: Dict[str, Dict[str, float]] = {}
    for pest in pests:
        insects = get_beneficial_insects(pest)
        rates: Dict[str, float] = {}
        for insect in insects:
            rate = get_beneficial_release_rate(insect)
            if rate is not None:
                rates[insect] = rate
        if rates:
            rec[pest] = rates
    return rec


def get_organic_controls(pest: str) -> List[str]:
    """Return organic control options for ``pest``."""

    return _ORGANIC.get(normalize_key(pest), [])


def recommend_organic_controls(pests: Iterable[str]) -> Dict[str, List[str]]:
    """Return organic control recommendations for observed ``pests``."""

    return {p: get_organic_controls(p) for p in pests}


def get_pest_lifecycle(pest: str) -> Dict[str, int]:
    """Return lifecycle stage durations in days for ``pest``."""

    data = _LIFECYCLE.get(normalize_key(pest))
    if not isinstance(data, Mapping):
        return {}
    result: Dict[str, int] = {}
    for stage, days in data.items():
        try:
            result[stage] = int(days)
        except (TypeError, ValueError):
            continue
    return result


def get_monitoring_interval(plant_type: str, stage: str | None = None) -> int | None:
    """Return scouting interval in days for a plant stage."""

    value = stage_value(_MONITORING, plant_type, stage)
    return int(value) if isinstance(value, (int, float)) else None


def get_pest_threshold(
    plant_type: str, pest: str, stage: str | None = None
) -> int | None:
    """Return pest count threshold triggering action."""

    if stage:
        crop = _STAGE_THRESHOLDS.get(normalize_key(plant_type), {})
        stage_data = crop.get(normalize_key(stage))
        if isinstance(stage_data, Mapping):
            value = stage_data.get(normalize_key(pest))
            if isinstance(value, (int, float)):
                return int(value)

    crop = _THRESHOLDS.get(normalize_key(plant_type), {})
    value = crop.get(normalize_key(pest))
    return int(value) if isinstance(value, (int, float)) else None


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
        if isinstance(factor, (int, float)) and factor > 0:
            base = round(base * float(factor))
    return int(base)


def build_monitoring_plan(
    plant_type: str,
    pests: Iterable[str],
    stage: str | None = None,
    risk_level: str | None = None,
) -> Dict[str, Any]:
    """Return monitoring interval, thresholds and methods for ``pests``."""

    interval = recommend_monitoring_interval(plant_type, stage, risk_level)
    thresholds: Dict[str, int] = {}
    methods: Dict[str, str] = {}
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


def get_pest_prevention(plant_type: str) -> Dict[str, str]:
    """Return pest prevention guidelines for ``plant_type``."""
    return _PREVENTION.get(normalize_key(plant_type), {})


def recommend_prevention(plant_type: str, pests: Iterable[str]) -> Dict[str, str]:
    """Return preventative actions for each observed pest."""
    guide = get_pest_prevention(plant_type)
    actions: Dict[str, str] = {}
    for pest in pests:
        actions[pest] = guide.get(pest, "No guideline available")
    return actions


def get_ipm_guidelines(plant_type: str) -> Dict[str, str]:
    """Return integrated pest management guidance for a crop."""
    return _IPM.get(normalize_key(plant_type), {})


def recommend_ipm_actions(plant_type: str, pests: Iterable[str] | None = None) -> Dict[str, str]:
    """Return IPM actions for the crop and specific pests if provided."""
    data = get_ipm_guidelines(plant_type)
    if not data:
        return {}
    actions: Dict[str, str] = {}
    general = data.get("general")
    if general:
        actions["general"] = general
    if pests:
        for pest in pests:
            action = data.get(normalize_key(pest))
            if action:
                actions[pest] = action
    return actions


def build_pest_management_plan(
    plant_type: str, pests: Iterable[str]
) -> Dict[str, Any]:
    """Return a consolidated IPM plan for ``plant_type`` and ``pests``.

    The returned mapping contains a ``"general"`` entry when overall IPM
    guidance is available. Each pest key maps to a dictionary with keys
    ``treatment``, ``prevention``, ``beneficials`` and ``ipm``.
    """

    pest_list = [normalize_key(p) for p in pests]

    plan: Dict[str, Any] = {}

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
        plan[pest] = {
            "treatment": treatments.get(pest, "No guideline available"),
            "prevention": prevention.get(pest, "No guideline available"),
            "beneficials": beneficials.get(pest, []),
            "ipm": ipm_actions.get(pest),
            "organic": organic.get(pest, []),
            "scientific_name": get_scientific_name(pest),
            "lifecycle": get_pest_lifecycle(pest),
        }

    return plan


__all__ = [
    "list_supported_plants",
    "get_pest_guidelines",
    "list_known_pests",
    "list_supported_pests",
    "get_scientific_name",
    "recommend_treatments",
    "get_beneficial_insects",
    "recommend_beneficials",
    "get_beneficial_release_rate",
    "recommend_release_rates",
    "get_organic_controls",
    "recommend_organic_controls",
    "get_pest_lifecycle",
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
]
