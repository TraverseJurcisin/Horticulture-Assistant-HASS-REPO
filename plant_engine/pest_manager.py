"""Pest management guideline utilities."""
import os
from typing import Dict
from .utils import load_json

DATA_PATH = os.path.join("data", "pest_guidelines.json")


def get_pest_guidelines(plant_type: str) -> Dict[str, str]:
    """Return pest management guidelines for the specified plant type."""
    if not os.path.exists(DATA_PATH):
        return {}
    data = load_json(DATA_PATH)
    return data.get(plant_type, {})
