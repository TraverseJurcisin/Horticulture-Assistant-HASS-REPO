"""Access to general environment management tips."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import lazy_dataset, normalize_key, list_dataset_entries

DATA_FILE = "environment_tips.yaml"

# lazily loaded dataset
_DATA = lazy_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_environment_tips",
]


def list_supported_plants() -> list[str]:
    """Return plant types with environment tips defined."""
    return list_dataset_entries(_DATA())


@lru_cache(maxsize=None)
def get_environment_tips(plant_type: str) -> Dict[str, str]:
    """Return environment management tips for ``plant_type``."""
    return _DATA().get(normalize_key(plant_type), {})

