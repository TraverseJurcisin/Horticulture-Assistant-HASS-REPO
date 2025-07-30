"""Wrapper for advanced growth index logic."""
from __future__ import annotations

from typing import Mapping, Dict

from custom_components.horticulture_assistant.utils.growth_model import (
    update_growth_index as _advanced_update,
)

# Compatibility constants preserved for tests
GROWTH_DIR = "data/growth"
YIELD_DIR = "data/yield"


def update_growth_index(
    plant_id: str,
    env_data: Mapping,
    transpiration_ml: float,
) -> Dict:
    """Return vegetative growth index using the shared util implementation."""
    return _advanced_update(None, plant_id, dict(env_data), transpiration_ml)
