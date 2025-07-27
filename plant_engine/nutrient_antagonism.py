"""Nutrient antagonism adjustments for fertilizer recommendations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

from .utils import load_dataset, list_dataset_entries

DATA_FILE = "nutrient_antagonisms.json"

@dataclass(frozen=True)
class AntagonismInfo:
    factor: float
    message: str = ""

_DATA: Dict[str, Dict[str, object]] = load_dataset(DATA_FILE)
_ANTAGONISM_MAP: Dict[Tuple[str, str], AntagonismInfo] = {}
for key, info in _DATA.items():
    if not isinstance(info, Mapping):
        continue
    try:
        n1, n2 = key.split("_")
        factor = float(info.get("factor", 1.0))
        msg = str(info.get("message", ""))
        _ANTAGONISM_MAP[(n1, n2)] = AntagonismInfo(factor=factor, message=msg)
    except Exception:
        continue

__all__ = [
    "list_antagonism_pairs",
    "get_antagonism_info",
    "get_antagonism_factor",
    "apply_antagonism_adjustments",
]


def list_antagonism_pairs() -> list[str]:
    """Return all nutrient pairs with antagonism data."""
    return list_dataset_entries(_DATA)


def get_antagonism_info(pair: str) -> Dict[str, object]:
    """Return raw antagonism entry for ``pair`` if defined."""
    return _DATA.get(pair.lower(), {})


def get_antagonism_factor(n1: str, n2: str) -> float | None:
    """Return antagonism factor for nutrients ``n1`` and ``n2`` if available."""
    info = _ANTAGONISM_MAP.get((n1.lower(), n2.lower())) or _ANTAGONISM_MAP.get(
        (n2.lower(), n1.lower())
    )
    return info.factor if info else None


def apply_antagonism_adjustments(levels: Mapping[str, float]) -> Dict[str, float]:
    """Return ``levels`` adjusted using defined antagonism factors."""
    result = {k: float(v) for k, v in levels.items()}
    key_map = {k.lower(): k for k in levels}
    for (n1, n2), info in _ANTAGONISM_MAP.items():
        if n1.lower() in key_map and n2.lower() in key_map:
            target = key_map[n2.lower()]
            result[target] = round(result[target] * info.factor, 2)
    return result
