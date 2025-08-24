from __future__ import annotations

"""Utilities for looking up fertilizer analysis data from the WSDA database."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache

try:
    from . import wsda_loader
except ImportError:  # pragma: no cover - fallback when run as script
    from plant_engine import wsda_loader  # type: ignore

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

    product_id: str
    name: str
    wsda_reg_no: str
    npk: tuple[float | None, float | None, float | None]


def _parse_analysis(raw: Mapping[str, object]) -> dict[str, float]:
    """Return numeric nutrient analysis from a raw WSDA mapping."""

    parsed: dict[str, float] = {}
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


@cache
def _records() -> Iterable[Mapping[str, object]]:
    """Return WSDA fertilizer records loaded from sharded index."""

    return tuple(wsda_loader.stream_index())


@cache
def _build_indexes() -> tuple[dict[str, _Product], dict[str, _Product]]:
    """Return lookup tables keyed by name and product number."""

    records = list(_records())
    if not records:
        return {}, {}

    names: dict[str, _Product] = {}
    numbers: dict[str, _Product] = {}
    for rec in records:
        name = str(rec.get("label_name", "")).strip()
        number = rec.get("wsda_reg_no", "")
        prod_id = rec.get("product_id", "")
        npk = (rec.get("n"), rec.get("p"), rec.get("k"))
        product = _Product(product_id=prod_id, name=name, wsda_reg_no=number, npk=npk)
        if name:
            names[name.lower()] = product
        if number:
            numbers[str(number)] = product

    return names, numbers


def _extract_npk(prod: _Product | None) -> dict[str, float]:
    if not prod:
        return {}
    n, p, k = prod.npk
    result = {}
    if n is not None:
        result["N"] = float(n)
    if p is not None:
        result["P"] = float(p)
    if k is not None:
        result["K"] = float(k)
    return result


@cache
def _load_analysis(product_id: str) -> dict[str, float]:
    try:
        detail = wsda_loader.load_detail(product_id)
    except FileNotFoundError:
        return {}
    ga = {}
    comp = detail.get("composition", {})
    if isinstance(comp, Mapping):
        ga = comp.get("guaranteed_analysis", {}) or {}
    if not ga:
        src = detail.get("source_wsda_record", {})
        if isinstance(src, Mapping):
            ga = src.get("guaranteed_analysis", {}) or {}
    return _parse_analysis(ga)


def _extract_analysis(prod: _Product | None) -> dict[str, float]:
    """Return the full nutrient analysis for ``prod`` if available."""
    if not prod:
        return {}
    return _load_analysis(prod.product_id)


def get_product_npk_by_name(name: str) -> dict[str, float]:
    """Return N, P and K percentages for a product ``name``.

    Matching is case-insensitive and the full product name should be supplied.
    An empty dictionary is returned if the product cannot be found.
    """
    name_l = name.lower()
    names, _ = _build_indexes()
    return _extract_npk(names.get(name_l))


def get_product_npk_by_number(number: str) -> dict[str, float]:
    """Return NPK percentages for a WSDA ``number`` such as ``(#4083-0001)``."""
    _, numbers = _build_indexes()
    return _extract_npk(numbers.get(number))


def get_product_analysis_by_name(name: str) -> dict[str, float]:
    """Return the complete guaranteed analysis for ``name``."""
    name_l = name.lower()
    names, _ = _build_indexes()
    return _extract_analysis(names.get(name_l))


def get_product_analysis_by_number(number: str) -> dict[str, float]:
    """Return guaranteed analysis for a WSDA ``number``."""
    _, numbers = _build_indexes()
    return _extract_analysis(numbers.get(number))


def search_products(query: str, limit: int = 10) -> list[str]:
    """Return product names containing ``query`` case-insensitively."""
    q = query.lower()
    names, _ = _build_indexes()
    matches = [prod.name for key, prod in names.items() if q in key]
    matches.sort()
    return matches[: max(limit, 0)]


def list_product_names() -> list[str]:
    """Return all product names sorted alphabetically."""
    names, _ = _build_indexes()
    return sorted(prod.name for prod in names.values())


def list_product_numbers() -> list[str]:
    """Return all WSDA product numbers sorted alphabetically."""
    _, numbers = _build_indexes()
    return sorted(numbers.keys())


def recommend_products_for_nutrient(nutrient: str, limit: int = 5) -> list[str]:
    """Return product names with the highest percentage of ``nutrient``.

    The search is case-insensitive and results are sorted by nutrient
    concentration in descending order.
    """
    n = nutrient.upper().strip()
    names, _ = _build_indexes()
    ranked = []
    for prod in names.values():
        analysis = _load_analysis(prod.product_id)
        value = analysis.get(n)
        if value is not None:
            ranked.append((prod.name, value))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in ranked[: max(limit, 0)]]
