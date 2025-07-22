"""Utilities for analyzing nutrient interaction ratios."""
from __future__ import annotations

from typing import Dict, Mapping

from .utils import load_dataset

DATA_FILE = "nutrient_interactions.json"

_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)

__all__ = ["list_interactions", "get_interaction_info", "check_imbalances"]


def list_interactions() -> list[str]:
    """Return all defined nutrient interaction pairs."""
    return sorted(_DATA.keys())


def get_interaction_info(pair: str) -> Dict[str, object]:
    """Return dataset entry for ``pair`` if available."""
    return _DATA.get(pair, {})


def check_imbalances(levels: Mapping[str, float]) -> Dict[str, str]:
    """Return warnings for nutrient ratios exceeding defined maxima."""
    warnings: Dict[str, str] = {}
    for pair, info in _DATA.items():
        if not isinstance(info, dict):
            continue
        max_ratio = info.get("max_ratio")
        if max_ratio is None:
            continue
        try:
            n1, n2 = pair.split("_")
        except ValueError:
            continue
        if n1 not in levels or n2 not in levels:
            continue
        val1 = levels[n1]
        val2 = levels[n2]
        try:
            ratio = float(val1) / float(val2)
        except Exception:
            continue
        if ratio > float(max_ratio):
            msg = str(info.get("message", "Imbalance detected"))
            warnings[f"{n1}/{n2}"] = msg
    return warnings

