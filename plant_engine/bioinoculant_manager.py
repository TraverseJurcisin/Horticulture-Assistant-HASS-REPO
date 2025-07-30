"""Helpers for recommending microbial inoculants by crop."""

from __future__ import annotations

from typing import List

from .utils import lazy_dataset, normalize_key, list_dataset_entries

DATA_FILE = "bioinoculants/bioinoculant_guidelines.json"

_data = lazy_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_inoculants",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with bioinoculant recommendations."""
    return list_dataset_entries(_data())


def get_recommended_inoculants(plant_type: str) -> List[str]:
    """Return microbial inoculants recommended for ``plant_type``."""
    return _data().get(normalize_key(plant_type), [])
