"""Pest management guideline utilities."""
import os
from typing import Dict
from functools import lru_cache
from .utils import load_json

DATA_PATH = os.path.join("data", "pest_guidelines.json")


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(DATA_PATH):
        return {}
    return load_json(DATA_PATH)


def get_pest_guidelines(plant_type: str) -> Dict[str, str]:
    """Return pest management guidelines for the specified plant type."""
    return _load_data().get(plant_type, {})
