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
    # additional commonly used datasets
    "ph_guidelines": "ph_guidelines.json",
    "pest_prevention": "pest_prevention.json",
    "nutrient_absorption_rates": "nutrient_absorption_rates.json",
    "nutrient_synergies": "nutrient_synergies.json",
}

__all__ = ["load_reference_data", "get_reference_dataset", "REFERENCE_FILES"]


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


def get_reference_dataset(name: str) -> Dict[str, Any]:
    """Return a single reference dataset by key.

    Parameters
    ----------
    name : str
        Dataset identifier from :data:`REFERENCE_FILES`.
    """

    filename = REFERENCE_FILES.get(name)
    if not filename:
        raise KeyError(name)
    content = load_dataset(filename)
    return content if isinstance(content, dict) else {}
