from __future__ import annotations

"""Utilities for looking up fertilizer analysis data from the WSDA database."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple, Mapping, Iterable

from plant_engine.utils import load_json

# Path to the WSDA fertilizer database packaged with the repository. Using
# :func:`load_dataset` allows overrides via ``HORTICULTURE_*`` environment
# variables to work as expected.
_WSDA_PATH = Path(__file__).resolve().parents[1] / "wsda_fertilizer_database.json"

__all__ = [
    "get_product_npk_by_name",
    "get_product_npk_by_number",
    "get_product_analysis_by_name",
    "get_product_analysis_by_number",
    "search_products",
    "list_product_names",
    "list_product_numbers",
    "recommend_products_for_nutrient",
]

@dataclass(frozen=True, slots=True)
class _Product:
    """Normalized fertilizer entry."""

    name: str
    npk: Tuple[float, float, float]
    analysis: Dict[str, float]


def _parse_analysis(raw: Mapping[str, object]) -> Dict[str, float]:
    """Return numeric nutrient analysis from a raw WSDA mapping."""

    parsed: Dict[str, float] = {}
    for key, value in raw.items():
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        if key.startswith("Total Nitrogen"):
            parsed["N"] = val
        elif "Phosphoric" in key:
            parsed["P"] = val
        elif "Potash" in key:
            parsed["K"] = val
        else:
            abbrev = key.split(" ")[0].replace("(", "").replace(")", "")
            parsed[abbrev] = val
    return parsed


@lru_cache(maxsize=None)
def _records() -> Iterable[Mapping[str, object]]:
    """Return WSDA fertilizer records loaded from the bundled JSON file."""

    if not _WSDA_PATH.exists():
        return []
    data = load_json(str(_WSDA_PATH))
    if isinstance(data, list):
        return data
    if isinstance(data, Mapping) and "records" in data:
        recs = data.get("records")
        if isinstance(recs, list):
            return recs
    return []


@lru_cache(maxsize=None)
def _build_indexes() -> Tuple[Dict[str, _Product], Dict[str, _Product]]:
    """Return lookup tables keyed by name and product number."""

    records = list(_records())
    if not records:
        return {}, {}

    names: Dict[str, _Product] = {}
    numbers: Dict[str, _Product] = {}
    for rec in records:
        ga_raw = rec.get("guaranteed_analysis", {})
        analysis = _parse_analysis(ga_raw)
        npk = (
            analysis.get("N", 0.0),
            analysis.get("P", 0.0),
            analysis.get("K", 0.0),
        )
        name = str(rec.get("product_name", "")).strip()
        number = rec.get("wsda_product_number")
        if name:
            names[name.lower()] = _Product(name=name, npk=npk, analysis=analysis)
        if number:
            numbers[str(number)] = _Product(name=name, npk=npk, analysis=analysis)

    return names, numbers


def _extract_npk(prod: _Product | None) -> Dict[str, float]:
    if not prod:
        return {}
    n, p, k = prod.npk
    return {"N": n, "P": p, "K": k}


def _extract_analysis(prod: _Product | None) -> Dict[str, float]:
    """Return the full nutrient analysis for ``prod`` if available."""
    return dict(prod.analysis) if prod else {}


def get_product_npk_by_name(name: str) -> Dict[str, float]:
    """Return N, P and K percentages for a product ``name``.

    Matching is case-insensitive and the full product name should be supplied.
    An empty dictionary is returned if the product cannot be found.
    """
    name_l = name.lower()
    names, _ = _build_indexes()
    return _extract_npk(names.get(name_l))


def get_product_npk_by_number(number: str) -> Dict[str, float]:
    """Return NPK percentages for a WSDA ``number`` such as ``(#4083-0001)``."""
    _, numbers = _build_indexes()
    return _extract_npk(numbers.get(number))


def get_product_analysis_by_name(name: str) -> Dict[str, float]:
    """Return the complete guaranteed analysis for ``name``."""
    name_l = name.lower()
    names, _ = _build_indexes()
    return _extract_analysis(names.get(name_l))


def get_product_analysis_by_number(number: str) -> Dict[str, float]:
    """Return guaranteed analysis for a WSDA ``number``."""
    _, numbers = _build_indexes()
    return _extract_analysis(numbers.get(number))


def search_products(query: str, limit: int = 10) -> List[str]:
    """Return product names containing ``query`` case-insensitively."""
    q = query.lower()
    names, _ = _build_indexes()
    matches = [prod.name for key, prod in names.items() if q in key]
    matches.sort()
    return matches[: max(limit, 0)]


def list_product_names() -> List[str]:
    """Return all product names sorted alphabetically."""
    names, _ = _build_indexes()
    return sorted(prod.name for prod in names.values())


def list_product_numbers() -> List[str]:
    """Return all WSDA product numbers sorted alphabetically."""
    _, numbers = _build_indexes()
    return sorted(numbers.keys())


def recommend_products_for_nutrient(nutrient: str, limit: int = 5) -> List[str]:
    """Return product names with the highest percentage of ``nutrient``.

    The search is case-insensitive and results are sorted by nutrient
    concentration in descending order.
    """
    n = nutrient.upper().strip()
    names, _ = _build_indexes()
    ranked = []
    for prod in names.values():
        value = prod.analysis.get(n)
        if value is not None:
            ranked.append((prod.name, value))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in ranked[: max(limit, 0)]]

