from __future__ import annotations

"""Lightweight access to the fertilizer products index."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any

try:
    from plant_engine import fertilizer_dataset_loader as dataset_loader
except ImportError:  # pragma: no cover - fallback when run as script
    from ..engine.plant_engine import fertilizer_dataset_loader as dataset_loader  # type: ignore

__all__ = [
    "ProductEntry",
    "list_products",
    "get_product_by_id",
    "get_product_by_number",
    "search_products",
]


@dataclass(frozen=True)
class ProductEntry:
    """Compact fertilizer product information."""

    product_id: str
    registration_number: str
    brand: str
    label_name: str
    formulation: str | None
    n: float | None
    p: float | None
    k: float | None


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _npk_from_composition(comp: Mapping[str, Any]) -> tuple[float | None, float | None, float | None]:
    npk_block = comp.get("npk")
    if not isinstance(npk_block, Mapping):
        return (None, None, None)

    basis = str(npk_block.get("basis") or "").lower()
    n = _coerce_float(npk_block.get("N_pct"))

    if basis == "oxide":
        p = _coerce_float(npk_block.get("P2O5_pct"))
        k = _coerce_float(npk_block.get("K2O_pct"))
    else:
        p = _coerce_float(npk_block.get("P_pct"))
        if p is None:
            p = _coerce_float(npk_block.get("P2O5_pct"))
        k = _coerce_float(npk_block.get("K_pct"))
        if k is None:
            k = _coerce_float(npk_block.get("K2O_pct"))

    return (n, p, k)


def _parse_record(rec: Mapping[str, object]) -> ProductEntry:
    product_id = str(rec.get("id") or rec.get("product_id") or "").strip()
    product_block = rec.get("product") if isinstance(rec.get("product"), Mapping) else {}
    metadata = rec.get("metadata") if isinstance(rec.get("metadata"), Mapping) else {}
    composition = rec.get("composition") if isinstance(rec.get("composition"), Mapping) else {}

    registration_number = str(metadata.get("wsda_reg_no") or "").strip()
    brand = str((product_block or {}).get("brand") or rec.get("brand") or "").strip()
    label_name = str((product_block or {}).get("name") or rec.get("label_name") or "").strip()

    formulation = metadata.get("formulation", rec.get("formulation"))
    if isinstance(formulation, str):
        formulation = formulation.strip()
    if formulation == "":
        formulation = None

    if composition:
        n, p, k = _npk_from_composition(composition)
    else:
        n = _coerce_float(rec.get("n"))
        p = _coerce_float(rec.get("p"))
        k = _coerce_float(rec.get("k"))

    return ProductEntry(
        product_id=product_id,
        registration_number=registration_number,
        brand=brand,
        label_name=label_name,
        formulation=formulation,
        n=n,
        p=p,
        k=k,
    )


@cache
def _load_index() -> tuple[dict[str, ProductEntry], dict[str, ProductEntry], list[ProductEntry]]:
    """Return lookup maps keyed by product_id and registration number."""

    by_id: dict[str, ProductEntry] = {}
    by_no: dict[str, ProductEntry] = {}
    items: list[ProductEntry] = []

    for rec in dataset_loader.stream_index():
        item = _parse_record(rec)
        if item.product_id:
            by_id[item.product_id] = item
        if item.registration_number:
            by_no[item.registration_number] = item
        items.append(item)

    return by_id, by_no, items


def list_products() -> list[ProductEntry]:
    """Return all products from the index."""
    _, _, items = _load_index()
    return list(items)


def get_product_by_id(product_id: str) -> ProductEntry | None:
    """Return a product record by internal ``product_id``."""
    by_id, _, _ = _load_index()
    return by_id.get(product_id)


def get_product_by_number(number: str) -> ProductEntry | None:
    """Return a product record by fertilizer registration number."""
    _, by_no, _ = _load_index()
    return by_no.get(number)


def _match_query(item: ProductEntry, query: str, fields: Iterable[str]) -> bool:
    q = query.lower()
    for field in fields:
        value = getattr(item, field, "")
        if q in str(value).lower():
            return True
    return False


def search_products(
    query: str, *, fields: Iterable[str] = ("label_name", "brand"), limit: int = 10
) -> list[ProductEntry]:
    """Return products matching ``query`` in any of the specified ``fields``."""
    if not query:
        return []
    _, _, items = _load_index()
    matches = [i for i in items if _match_query(i, query, fields)]
    matches.sort(key=lambda x: x.label_name)
    return matches[: max(limit, 0)]
