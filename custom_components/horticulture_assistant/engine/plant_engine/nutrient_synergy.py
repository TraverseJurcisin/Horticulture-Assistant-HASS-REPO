"""Utility helpers for nutrient synergy adjustments."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .utils import list_dataset_entries, load_dataset

DATA_FILE = "nutrients/nutrient_synergies.json"


@dataclass(frozen=True)
class SynergyInfo:
    """Normalized dataset entry for a nutrient pair."""

    factor: float
    message: str = ""


_DATA: dict[str, dict[str, object]] = load_dataset(DATA_FILE)

# Pre-compute a case-insensitive lookup map for faster runtime access
_SYNERGY_MAP: dict[tuple[str, str], SynergyInfo] = {
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
    "has_synergy_pair",
    "apply_synergy_adjustments",
    "apply_synergy_adjustments_verbose",
]


def list_synergy_pairs() -> list[str]:
    """Return all nutrient pairs with synergy data."""
    return list_dataset_entries(_DATA)


def get_synergy_info(pair: str) -> dict[str, object]:
    """Return raw synergy entry for ``pair`` if defined."""
    return _DATA.get(pair.lower(), {})


def get_synergy_factor(n1: str, n2: str) -> float | None:
    """Return synergy factor for nutrients ``n1`` and ``n2`` if available."""
    n1_key = n1.casefold()
    n2_key = n2.casefold()
    info = _SYNERGY_MAP.get((n1_key, n2_key)) or _SYNERGY_MAP.get((n2_key, n1_key))
    return info.factor if info else None


def has_synergy_pair(n1: str, n2: str) -> bool:
    """Return ``True`` if synergy data exists for the nutrient pair."""
    n1_key = n1.casefold()
    n2_key = n2.casefold()
    return (n1_key, n2_key) in _SYNERGY_MAP or (n2_key, n1_key) in _SYNERGY_MAP


def apply_synergy_adjustments(levels: Mapping[str, float]) -> dict[str, float]:
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
) -> tuple[dict[str, float], dict[str, str]]:
    """Return adjusted levels with messages describing each applied synergy."""

    adjusted = {k: float(v) for k, v in levels.items()}
    notes: dict[str, str] = {}

    key_map = {k.casefold(): k for k in levels}

    for (n1, n2), info in _SYNERGY_MAP.items():
        if n1 in key_map and n2 in key_map:
            target = key_map[n2]
            adjusted[target] = round(adjusted[target] * info.factor, 2)
            if info.message:
                notes[f"{n1}/{n2}"] = info.message

    return adjusted, notes
