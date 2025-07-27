"""Nutrient synergy adjustments for fertilizer recommendations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

from .utils import load_dataset, list_dataset_entries

DATA_FILE = "nutrient_synergies.json"

@dataclass(frozen=True)
class SynergyInfo:
    factor: float
    message: str = ""

_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)
_SYNERGY_MAP: Dict[Tuple[str, str], SynergyInfo] = {}
for key, info in _DATA.items():
    if not isinstance(info, Mapping):
        continue
    try:
        n1, n2 = key.split("_")
        factor = float(info.get("factor", 1.0))
        msg = str(info.get("message", ""))
        _SYNERGY_MAP[(n1, n2)] = SynergyInfo(factor=factor, message=msg)
    except Exception:
        continue

__all__ = [
    "list_synergy_pairs",
    "get_synergy_info",
    "get_synergy_factor",
    "apply_synergy_adjustments",
]


def list_synergy_pairs() -> list[str]:
    """Return all nutrient pairs with synergy data."""
    return list_dataset_entries(_DATA)


def get_synergy_info(pair: str) -> Dict[str, object]:
    """Return raw synergy entry for ``pair`` if defined."""
    return _DATA.get(pair.lower(), {})


def get_synergy_factor(n1: str, n2: str) -> float | None:
    """Return synergy factor for nutrients ``n1`` and ``n2`` if available."""
    info = _SYNERGY_MAP.get((n1.lower(), n2.lower())) or _SYNERGY_MAP.get(
        (n2.lower(), n1.lower())
    )
    return info.factor if info else None


def apply_synergy_adjustments(levels: Mapping[str, float]) -> Dict[str, float]:
    """Return ``levels`` adjusted using defined synergy factors."""
    result = {k: float(v) for k, v in levels.items()}
    lookup = {k.lower(): k for k in levels}
    for (n1, n2), info in _SYNERGY_MAP.items():
        if n1 in lookup and n2 in lookup:
            key = lookup[n2]
            result[key] = round(result[key] * info.factor, 2)
    return result
