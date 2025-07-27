"""Access to general environment management tips."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import (
    lazy_dataset,
    list_dataset_entries,
    normalize_key,
    clear_dataset_cache,
)

DATA_FILE = "environment_tips.yaml"

# Lazy loader so importing this module has minimal overhead
_DATA = lazy_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_environment_tips",
    "refresh_cache",
]


def list_supported_plants() -> list[str]:
    """Return plant types with environment tips defined."""
    return list_dataset_entries(_DATA())


@lru_cache(maxsize=None)
def get_environment_tips(plant_type: str) -> Dict[str, str]:
    """Return environment management tips for ``plant_type``."""
    return _DATA().get(normalize_key(plant_type), {})


def refresh_cache() -> None:
    """Clear cached dataset values."""
    clear_dataset_cache()
    _DATA.cache_clear()
    get_environment_tips.cache_clear()

