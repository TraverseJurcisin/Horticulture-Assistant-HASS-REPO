"""Convenient access to common horticultural reference datasets."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from .utils import load_dataset

REFERENCE_FILES = {
    "nutrient_guidelines": "nutrient_guidelines.json",
    "environment_guidelines": "environment_guidelines.json",
    "pest_guidelines": "pest_guidelines.json",
    "growth_stages": "growth_stages.json",
}

__all__ = ["load_reference_data", "REFERENCE_FILES"]


@lru_cache(maxsize=None)
def load_reference_data() -> Dict[str, Dict[str, Any]]:
    """Return consolidated horticultural reference data.

    The resulting mapping caches dataset contents so subsequent calls avoid
    additional disk reads.
    """

    data: Dict[str, Dict[str, Any]] = {}
    for key, filename in REFERENCE_FILES.items():
        content = load_dataset(filename)
        data[key] = content if isinstance(content, dict) else {}
    return data
