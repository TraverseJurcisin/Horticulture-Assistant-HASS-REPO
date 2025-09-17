from __future__ import annotations

"""Utilities for looking up fertilizer analysis data from the fertilizer dataset."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any

try:
    from . import fertilizer_dataset_loader as dataset_loader
except ImportError:  # pragma: no cover - fallback when run as script
    from plant_engine import fertilizer_dataset_loader as dataset_loader  # type: ignore

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
    registration_number: str
    npk: tuple[float | None, float | None, float | None]


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _npk_from_composition(comp: Mapping[str, Any]) -> tuple[float | None, float | None, float | None]:
    npk_block = comp.get("npk")
    if not isinstance(npk_block, Mapping):
        return (None, None, None)

    n = _coerce_float(npk_block.get("N_pct"))

    p = _coerce_float(npk_block.get("P_pct"))
    if p is None:
        p = _coerce_float(npk_block.get("P2O5_pct"))

    k = _coerce_float(npk_block.get("K_pct"))
    if k is None:
        k = _coerce_float(npk_block.get("K2O_pct"))

    return (n, p, k)


def _analysis_from_composition(comp: Mapping[str, Any]) -> dict[str, float]:
    """Convert a schema ``composition`` mapping into flat nutrient analysis."""

    analysis: dict[str, float] = {}
    n, p, k = _npk_from_composition(comp)
    if n is not None:
        analysis["N"] = n
    if p is not None:
        analysis["P"] = p
    if k is not None:
        analysis["K"] = k

    macros = comp.get("macros_pct")
    if isinstance(macros, Mapping):
        for key in ("Ca", "Mg", "S"):
            value = _coerce_float(macros.get(key))
            if value is not None:
                analysis[key] = value

    micros = comp.get("micros_pct")
    if isinstance(micros, Mapping):
        for key, value in micros.items():
            val = _coerce_float(value)
            if val is not None:
                analysis[key] = val

    return analysis


def _normalize_index_record(rec: Mapping[str, object]) -> _Product | None:
    """Return a standard :class:`_Product` from schema index rows."""

    product_id = str(rec.get("id") or rec.get("product_id") or "").strip()
    product = rec.get("product") if isinstance(rec.get("product"), Mapping) else {}
    metadata = rec.get("metadata") if isinstance(rec.get("metadata"), Mapping) else {}
    composition = rec.get("composition") if isinstance(rec.get("composition"), Mapping) else {}

    name = str((product or {}).get("name") or "").strip()
    registration_number = str(metadata.get("wsda_reg_no") or "").strip()
    npk = _npk_from_composition(composition)

    if not product_id and not name:
        return None

    return _Product(product_id=product_id, name=name, registration_number=registration_number, npk=npk)


@cache
def _records() -> Iterable[Mapping[str, object]]:
    """Return fertilizer dataset records loaded from sharded index."""

    return tuple(dataset_loader.stream_index())


@cache
def _build_indexes() -> tuple[dict[str, _Product], dict[str, _Product]]:
    """Return lookup tables keyed by name and product number."""

    records = list(_records())
    if not records:
        return {}, {}

    names: dict[str, _Product] = {}
    numbers: dict[str, _Product] = {}
    for rec in records:
        product = _normalize_index_record(rec)
        if not product:
            continue
        if product.name:
            names[product.name.lower()] = product
        if product.registration_number:
            numbers[product.registration_number] = product

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
        detail = dataset_loader.load_detail(product_id)
    except FileNotFoundError:
        return {}
    if not isinstance(detail, Mapping):
        return {}
    comp = detail.get("composition")
    if not isinstance(comp, Mapping):
        return {}
    return _analysis_from_composition(comp)


@cache
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
    """Return NPK percentages for a fertilizer registration number such as ``(#4083-0001)``."""
    _, numbers = _build_indexes()
    return _extract_npk(numbers.get(number))


def get_product_analysis_by_name(name: str) -> dict[str, float]:
    """Return the complete nutrient analysis for ``name``."""
    name_l = name.lower()
    names, _ = _build_indexes()
    return _extract_analysis(names.get(name_l))


def get_product_analysis_by_number(number: str) -> dict[str, float]:
    """Return nutrient analysis for a fertilizer registration number."""
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
    """Return all fertilizer registration numbers sorted alphabetically."""
    _, numbers = _build_indexes()
    return sorted(numbers.keys())


def recommend_products_for_nutrient(nutrient: str, limit: int = 5) -> list[str]:
    """Return product names with the highest percentage of ``nutrient``.

    The search is case-insensitive and results are sorted by nutrient
    concentration in descending order.
    """
    n_key = nutrient.upper().strip()
    names, _ = _build_indexes()
    ranked: list[tuple[str, float]] = []
    for prod in names.values():
        analysis = _load_analysis(prod.product_id)
        value = analysis.get(n_key)
        if value is not None:
            ranked.append((prod.name, value))

    ranked.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in ranked[: max(limit, 0)]]
