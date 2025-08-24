"""Helpers for recommending microbial inoculants by crop."""

from __future__ import annotations

from .utils import lazy_dataset, list_dataset_entries, normalize_key

DATA_FILE = "bioinoculants/bioinoculant_guidelines.json"

_data = lazy_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_recommended_inoculants",
]


def list_supported_plants() -> list[str]:
    """Return all plant types with bioinoculant recommendations."""
    return list_dataset_entries(_data())


def get_recommended_inoculants(plant_type: str) -> list[str]:
    """Return microbial inoculants recommended for ``plant_type``."""
    return _data().get(normalize_key(plant_type), [])
