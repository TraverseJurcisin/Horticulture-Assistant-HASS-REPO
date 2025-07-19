"""Environment guideline utilities."""
from typing import Dict, Any
import os
from .utils import load_json

DATA_PATH = os.path.join("data", "environment_guidelines.json")


def get_environmental_targets(plant_type: str, stage: str | None = None) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    if not os.path.exists(DATA_PATH):
        return {}
    data = load_json(DATA_PATH).get(plant_type, {})
    if stage:
        stage = stage.lower()
        if stage in data:
            return data[stage]
    return data.get("optimal", {})
