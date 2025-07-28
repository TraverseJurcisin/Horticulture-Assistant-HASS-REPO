"""Utility helpers for nutrient synergy adjustments."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple, Iterable

from .utils import load_dataset, list_dataset_entries

DATA_FILE = "nutrient_synergies.json"

@dataclass(frozen=True)
class SynergyInfo:
    """Normalized dataset entry for a nutrient pair."""

    factor: float
    message: str = ""


_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)

# Pre-compute a case-insensitive lookup map for faster runtime access
_SYNERGY_MAP: Dict[Tuple[str, str], SynergyInfo] = {
    tuple(part.casefold() for part in key.split("_", 1)): SynergyInfo(
        factor=float(info.get("factor", 1.0)),
        message=str(info.get("message", "")),
    )
    for key, info in _DATA.items()
    if isinstance(info, Mapping) and "_" in key
}

__all__ = [
    "list_synergy_pairs",
    "get_synergy_info",
    "get_synergy_factor",
    "apply_synergy_adjustments",
    "apply_synergy_adjustments_verbose",
]


def list_synergy_pairs() -> list[str]:
    """Return all nutrient pairs with synergy data."""
    return list_dataset_entries(_DATA)


def get_synergy_info(pair: str) -> Dict[str, object]:
    """Return raw synergy entry for ``pair`` if defined."""
    return _DATA.get(pair.lower(), {})


def get_synergy_factor(n1: str, n2: str) -> float | None:
    """Return synergy factor for nutrients ``n1`` and ``n2`` if available."""
    n1_key = n1.casefold()
    n2_key = n2.casefold()
    info = _SYNERGY_MAP.get((n1_key, n2_key)) or _SYNERGY_MAP.get((n2_key, n1_key))
    return info.factor if info else None


def apply_synergy_adjustments(levels: Mapping[str, float]) -> Dict[str, float]:
    """Return ``levels`` adjusted using defined synergy factors."""
    result = {k: float(v) for k, v in levels.items()}

    key_map = {k.casefold(): k for k in levels}

    for (n1, n2), info in _SYNERGY_MAP.items():
        if n1 in key_map and n2 in key_map:
            target = key_map[n2]
            result[target] = round(result[target] * info.factor, 2)

    return result


def apply_synergy_adjustments_verbose(
    levels: Mapping[str, float],
) -> tuple[Dict[str, float], Dict[str, str]]:
    """Return adjusted levels with messages describing each applied synergy."""

    adjusted = {k: float(v) for k, v in levels.items()}
    notes: Dict[str, str] = {}

    key_map = {k.casefold(): k for k in levels}

    for (n1, n2), info in _SYNERGY_MAP.items():
        if n1 in key_map and n2 in key_map:
            target = key_map[n2]
            adjusted[target] = round(adjusted[target] * info.factor, 2)
            if info.message:
                notes[f"{n1}/{n2}"] = info.message

    return adjusted, notes
