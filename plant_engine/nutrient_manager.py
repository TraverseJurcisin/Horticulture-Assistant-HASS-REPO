"""Nutrient requirement helper functions."""
from typing import Dict
import os
from plant_engine.utils import load_json

DATA_PATH = os.path.join("data", "nutrient_guidelines.json")


def get_recommended_levels(plant_type: str, stage: str) -> Dict[str, float]:
    """Return recommended nutrient levels for the given plant type and stage."""
    if not os.path.exists(DATA_PATH):
        return {}
    data = load_json(DATA_PATH)
    return data.get(plant_type, {}).get(stage, {})
