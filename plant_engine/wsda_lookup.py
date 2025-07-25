"""Utilities for looking up fertilizer analysis data from the WSDA database."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple, Mapping, Iterable

from plant_engine.utils import load_json

# Repository root used to locate the sharded WSDA dataset
_ROOT = Path(__file__).resolve().parents[1]
# Compact index of product records
_INDEX_PATH = _ROOT / "products_index.jsonl"
# Detailed records directory grouped by the first two characters of ``product_id``
_DETAIL_DIR = _ROOT / "feature" / "wsda_refactored_sharded" / "detail"


def _load_detail(product_id: str) -> Mapping[str, object] | None:
    """Return parsed detail record for ``product_id`` if available."""

    if not product_id:
        return None
    path = _DETAIL_DIR / product_id[:2] / f"{product_id}.json"
    if not path.exists():
        return None
    return load_json(str(path))

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

@dataclass(frozen=True)
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
    """Return WSDA fertilizer records merged from the index and detail files."""

    if not _INDEX_PATH.exists():
        return []

    records = []
    with open(_INDEX_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            idx = json.loads(line)
            product_id = idx.get("product_id", "")
            name = idx.get("label_name", "")
            number = idx.get("wsda_reg_no")

            analysis: Dict[str, float] = {}
            if (val := idx.get("n")) is not None:
                analysis["N"] = float(val)
            if (val := idx.get("p")) is not None:
                analysis["P"] = float(val)
            if (val := idx.get("k")) is not None:
                analysis["K"] = float(val)

            detail = _load_detail(product_id)
            if detail:
                ga = detail.get("source_wsda_record", {}).get(
                    "guaranteed_analysis", {}
                )
                analysis.update(_parse_analysis(ga))

            records.append(
                {
                    "product_name": name,
                    "wsda_product_number": number,
                    "guaranteed_analysis": analysis,
                }
            )

    return records


@lru_cache(maxsize=None)
def _build_indexes() -> Tuple[Dict[str, _Product], Dict[str, _Product]]:
    """Return lookup tables keyed by name and product number."""

    records = list(_records())
    if not records:
        return {}, {}

    names: Dict[str, _Product] = {}
    numbers: Dict[str, _Product] = {}
    for rec in records:
        analysis = dict(rec.get("guaranteed_analysis", {}))
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

