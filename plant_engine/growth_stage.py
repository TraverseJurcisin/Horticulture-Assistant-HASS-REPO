"""Retrieve growth stage metadata for plants."""
from __future__ import annotations

from typing import Dict, Any
from functools import lru_cache
from .utils import load_dataset

DATA_FILE = "growth_stages.json"


@lru_cache(maxsize=None)
def _load_data() -> Dict[str, Dict[str, Any]]:
    return load_dataset(DATA_FILE)


def get_stage_info(plant_type: str, stage: str) -> Dict[str, Any]:
    """Return information about a particular growth stage."""
    return _load_data().get(plant_type, {}).get(stage, {})
