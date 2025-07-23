"""Pest management guideline utilities."""
from __future__ import annotations

from typing import Dict, Iterable, List

from .utils import load_dataset, normalize_key

DATA_FILE = "pest_guidelines.json"
BENEFICIAL_FILE = "beneficial_insects.json"
PREVENTION_FILE = "pest_prevention.json"
IPM_FILE = "ipm_guidelines.json"



# Datasets are cached by ``load_dataset`` so loaded once at import time
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)
_BENEFICIALS: Dict[str, List[str]] = load_dataset(BENEFICIAL_FILE)
_PREVENTION: Dict[str, Dict[str, str]] = load_dataset(PREVENTION_FILE)
_IPM: Dict[str, Dict[str, str]] = load_dataset(IPM_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with pest guidelines."""
    return sorted(_DATA.keys())


def get_pest_guidelines(plant_type: str) -> Dict[str, str]:
    """Return pest management guidelines for the specified plant type."""
    return _DATA.get(normalize_key(plant_type), {})


def list_known_pests(plant_type: str) -> list[str]:
    """Return all pests with guidelines for ``plant_type``."""
    return sorted(get_pest_guidelines(plant_type).keys())


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


__all__ = [
    "list_supported_plants",
    "get_pest_guidelines",
    "list_known_pests",
    "recommend_treatments",
    "get_beneficial_insects",
    "recommend_beneficials",
    "get_pest_prevention",
    "recommend_prevention",
    "get_ipm_guidelines",
    "recommend_ipm_actions",
]
