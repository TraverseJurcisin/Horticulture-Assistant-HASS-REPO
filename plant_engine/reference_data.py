"""Convenient access to common horticultural reference datasets."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from .utils import load_dataset

# Mapping of logical keys to dataset file names used across the project.
# Additional datasets can be appended here without altering code that
# consumes :func:`load_reference_data` or :func:`get_reference_dataset`.
REFERENCE_FILES: dict[str, str] = {
    "nutrient_guidelines": "nutrient_guidelines.json",
    "environment_guidelines": "environment_guidelines.json",
    "pest_guidelines": "pest_guidelines.json",
    "growth_stages": "growth_stages.json",
    # newly exposed reference datasets
    "nutrient_synergies": "nutrient_synergies.json",
    "disease_guidelines": "disease_guidelines.json",
}

__all__ = ["load_reference_data", "get_reference_dataset", "REFERENCE_FILES"]


@lru_cache(maxsize=None)
def load_reference_data() -> Dict[str, Dict[str, Any]]:
    """Return consolidated horticultural reference datasets.

    Results are cached so repeated lookups do not trigger additional disk
    reads. The return value maps each key in :data:`REFERENCE_FILES` to the
    parsed dataset contents (or an empty ``dict`` if the file is missing or
    invalid).
    """

    data: Dict[str, Dict[str, Any]] = {}
    for key, filename in REFERENCE_FILES.items():
        content = load_dataset(filename)
        data[key] = content if isinstance(content, dict) else {}
    return data


def get_reference_dataset(name: str) -> Dict[str, Any]:
    """Return a specific reference dataset by ``name``."""

    return load_reference_data().get(name, {})
