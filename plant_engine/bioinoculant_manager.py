"""Helpers for recommending microbial inoculants by crop."""

from __future__ import annotations

from typing import Dict, List

from .utils import load_dataset, normalize_key, list_dataset_entries

DATA_FILE = "bioinoculant_guidelines.json"

_DATA: Dict[str, List[str]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_inoculants",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with bioinoculant recommendations."""
    return list_dataset_entries(_DATA)


def get_recommended_inoculants(plant_type: str) -> List[str]:
    """Return microbial inoculants recommended for ``plant_type``."""
    return _DATA.get(normalize_key(plant_type), [])
