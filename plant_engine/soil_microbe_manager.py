"""Lookup beneficial soil microorganisms for crops."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "soil_microbe_guidelines.json"

# cache dataset on first load
_DATA: Dict[str, List[str]] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_recommended_microbes"]


def list_supported_plants() -> List[str]:
    """Return all plant types with microbe recommendations."""
    return list_dataset_entries(_DATA)


@lru_cache(maxsize=None)
def get_recommended_microbes(plant_type: str) -> List[str]:
    """Return beneficial microbes recommended for ``plant_type``."""
    microbes = _DATA.get(normalize_key(plant_type), [])
    return [str(m) for m in microbes]
