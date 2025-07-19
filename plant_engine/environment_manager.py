"""Environment guideline utilities."""
from typing import Dict, Any
import os
from functools import lru_cache
from .utils import load_json

DATA_PATH = os.path.join("data", "environment_guidelines.json")


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_PATH):
        return {}
    return load_json(DATA_PATH)


def get_environmental_targets(plant_type: str, stage: str | None = None) -> Dict[str, Any]:
    """Return recommended environmental ranges for a plant type and stage."""
    data = _load_data().get(plant_type, {})
    if stage:
        stage = stage.lower()
        if stage in data:
            return data[stage]
    return data.get("optimal", {})
