from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

# Path to the WSDA fertilizer database packaged with the repository
_WSDA_PATH = Path(__file__).resolve().parents[1] / "wsda_fertilizer_database.json"

__all__ = [
    "get_product_npk_by_name",
    "get_product_npk_by_number",
]

@lru_cache(maxsize=None)
def _database() -> List[Dict[str, object]]:
    """Return parsed WSDA database records."""
    if not _WSDA_PATH.exists():
        return []
    with open(_WSDA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _match_record(predicate) -> Dict[str, object] | None:
    for item in _database():
        if predicate(item):
            return item
    return None


def _extract_npk(record: Dict[str, object]) -> Dict[str, float]:
    ga = record.get("guaranteed_analysis", {}) if record else {}
    return {
        "N": float(ga.get("Total Nitrogen (N)") or 0),
        "P": float(ga.get("Available Phosphoric Acid (P2O5)") or 0),
        "K": float(ga.get("Soluble Potash (K2O)") or 0),
    }


def get_product_npk_by_name(name: str) -> Dict[str, float]:
    """Return N, P and K percentages for a product ``name``.

    Matching is case-insensitive and the full product name should be supplied.
    An empty dictionary is returned if the product cannot be found.
    """
    name_l = name.lower()
    rec = _match_record(lambda d: d.get("product_name", "").lower() == name_l)
    return _extract_npk(rec)


def get_product_npk_by_number(number: str) -> Dict[str, float]:
    """Return NPK percentages for a WSDA ``number`` such as ``(#4083-0001)``."""
    rec = _match_record(lambda d: d.get("wsda_product_number") == number)
    return _extract_npk(rec)
