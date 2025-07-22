"""Disease management guideline utilities."""
from __future__ import annotations

from typing import Dict, Iterable

from .utils import load_dataset, normalize_key

DATA_FILE = "disease_guidelines.json"



# Dataset is cached by ``load_dataset`` so load once at import time
_DATA: Dict[str, Dict[str, str]] = load_dataset(DATA_FILE)


def list_supported_plants() -> list[str]:
    """Return all plant types with disease guidelines."""
    return sorted(_DATA.keys())


def get_disease_guidelines(plant_type: str) -> Dict[str, str]:
    """Return disease management guidelines for the specified plant type."""
    return _DATA.get(normalize_key(plant_type), {})


def recommend_treatments(plant_type: str, diseases: Iterable[str]) -> Dict[str, str]:
    """Return recommended treatment strings for each observed disease."""
    guide = get_disease_guidelines(plant_type)
    actions: Dict[str, str] = {}
    for dis in diseases:
        actions[dis] = guide.get(dis, "No guideline available")
    return actions
