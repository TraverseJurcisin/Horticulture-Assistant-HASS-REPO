"""Pest management guideline utilities."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable

from .utils import load_dataset

DATA_FILE = "pest_guidelines.json"


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Dict[str, str]]:
    return load_dataset(DATA_FILE)


def get_pest_guidelines(plant_type: str) -> Dict[str, str]:
    """Return pest management guidelines for the specified plant type."""
    return _load_data().get(plant_type, {})


def recommend_treatments(plant_type: str, pests: Iterable[str]) -> Dict[str, str]:
    """Return recommended treatment strings for each observed pest."""
    guide = get_pest_guidelines(plant_type)
    actions: Dict[str, str] = {}
    for pest in pests:
        actions[pest] = guide.get(pest, "No guideline available")
    return actions
