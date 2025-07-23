"""Utilities for detecting and correcting nutrient ratio imbalances."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset

_Pair = tuple[str, str]

DATA_FILE = "nutrient_interactions.json"
ACTION_FILE = "nutrient_interaction_actions.json"


_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)

# Precompute a mapping of nutrient pairs to interaction info for faster lookups
_PAIR_DATA: Dict[_Pair, Dict[str, object]] = {}
for _key, _info in _DATA.items():
    if not isinstance(_info, dict):
        continue
    try:
        n1, n2 = _key.split("_")
    except ValueError:
        continue
    _PAIR_DATA[(n1, n2)] = _info

_ACTIONS: Dict[str, str] = load_dataset(ACTION_FILE)

__all__ = [
    "list_interactions",
    "get_interaction_info",
    "get_max_ratio",
    "check_imbalances",
    "get_balance_action",
    "recommend_balance_actions",
]


def list_interactions() -> list[str]:
    """Return all defined nutrient interaction pairs."""
    return sorted(_DATA.keys())


def get_interaction_info(pair: str) -> Dict[str, object]:
    """Return dataset entry for ``pair`` if available."""
    return _DATA.get(pair, {})


def get_max_ratio(n1: str, n2: str) -> float | None:
    """Return the defined maximum ratio for two nutrients if available."""
    info = _PAIR_DATA.get((n1, n2)) or _PAIR_DATA.get((n2, n1))
    if info is None:
        return None
    value = info.get("max_ratio")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_imbalances(levels: Mapping[str, float]) -> Dict[str, str]:
    """Return warnings for nutrient ratios exceeding defined maxima."""
    warnings: Dict[str, str] = {}
    for (n1, n2), info in _PAIR_DATA.items():
        if n1 not in levels or n2 not in levels:
            continue
        val1 = levels[n1]
        val2 = levels[n2]
        try:
            ratio = float(val1) / float(val2)
            max_ratio = float(info.get("max_ratio", 0))
        except Exception:
            continue
        if ratio > max_ratio:
            msg = str(info.get("message", "Imbalance detected"))
            warnings[f"{n1}/{n2}"] = msg
    return warnings


def get_balance_action(pair: str) -> str:
    """Return recommended action string for an imbalanced nutrient pair."""
    key = pair.replace("/", "_")
    action = _ACTIONS.get(key)
    if action:
        return action
    n1, _, n2 = key.partition("_")
    rev_key = f"{n2}_{n1}" if n2 else key
    return _ACTIONS.get(rev_key, "")


def recommend_balance_actions(levels: Mapping[str, float]) -> Dict[str, str]:
    """Return actions for all detected nutrient imbalances."""

    warnings = check_imbalances(levels)
    actions: Dict[str, str] = {}
    for pair in warnings:
        action = get_balance_action(pair)
        if action:
            actions[pair] = action
    return actions

