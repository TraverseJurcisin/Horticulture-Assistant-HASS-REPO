"""Retrieve growth stage metadata for plants."""
from __future__ import annotations

import os
from typing import Dict, Any
from functools import lru_cache
from .utils import load_json

DATA_PATH = os.path.join("data", "growth_stages.json")


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(DATA_PATH):
        return {}
    return load_json(DATA_PATH)


def get_stage_info(plant_type: str, stage: str) -> Dict[str, Any]:
    """Return information about a particular growth stage."""
    return _load_data().get(plant_type, {}).get(stage, {})
