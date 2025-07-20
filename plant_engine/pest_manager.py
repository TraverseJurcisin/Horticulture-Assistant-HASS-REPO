"""Pest management guideline utilities."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset

DATA_FILE = "pest_guidelines.json"



# Dataset is cached by ``load_dataset`` so load once at import time
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with pest guidelines."""
    return sorted(_DATA.keys())


def get_pest_guidelines(plant_type: str) -> Dict[str, str]:
    """Return pest management guidelines for the specified plant type."""
    return _DATA.get(plant_type, {})


def recommend_treatments(plant_type: str, pests: Iterable[str]) -> Dict[str, str]:
    """Return recommended treatment strings for each observed pest."""
    guide = get_pest_guidelines(plant_type)
    actions: Dict[str, str] = {}
    for pest in pests:
        actions[pest] = guide.get(pest, "No guideline available")
    return actions
