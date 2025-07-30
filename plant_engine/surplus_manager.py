from __future__ import annotations

from typing import Dict, Mapping

from .nutrient_manager import calculate_all_surplus
from .utils import load_dataset

DATA_FILE = "nutrients/nutrient_surplus_actions.json"

_ACTIONS: Dict[str, str] = load_dataset(DATA_FILE)

__all__ = [
    "list_known_nutrients",
    "get_surplus_action",
    "recommend_surplus_actions",
]


def list_known_nutrients() -> list[str]:
    """Return nutrients with recorded surplus actions."""

    return sorted(_ACTIONS.keys())


def get_surplus_action(nutrient: str) -> str:
    """Return recommended action string for a nutrient surplus."""

    return _ACTIONS.get(nutrient, "")


def recommend_surplus_actions(
    current_levels: Mapping[str, float], plant_type: str, stage: str
) -> Dict[str, str]:
    """Return actions for nutrients exceeding recommended levels."""

    surplus = calculate_all_surplus(current_levels, plant_type, stage)
    actions: Dict[str, str] = {}
    for nutrient in surplus:
        action = get_surplus_action(nutrient)
        if action:
            actions[nutrient] = action
    return actions
