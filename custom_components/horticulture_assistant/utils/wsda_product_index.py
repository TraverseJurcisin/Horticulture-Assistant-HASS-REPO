from __future__ import annotations

"""Lightweight access to the WSDA fertilizer products index."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List

# Path to the newline-delimited JSON index packaged with the repository
_INDEX_PATH = Path(__file__).resolve().parents[3] / "products_index.jsonl"

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
    wsda_reg_no: str
    brand: str
    label_name: str
    formulation: str | None
    n: float | None
    p: float | None
    k: float | None


def _parse_line(line: str) -> ProductEntry:
    rec = json.loads(line)
    return ProductEntry(
        product_id=rec.get("product_id", ""),
        wsda_reg_no=rec.get("wsda_reg_no", ""),
        brand=rec.get("brand", ""),
        label_name=rec.get("label_name", ""),
        formulation=rec.get("formulation"),
        n=rec.get("n"),
        p=rec.get("p"),
        k=rec.get("k"),
    )


@lru_cache(maxsize=None)
def _load_index() -> tuple[Dict[str, ProductEntry], Dict[str, ProductEntry], List[ProductEntry]]:
    """Return lookup maps keyed by product_id and wsda_reg_no."""
    by_id: Dict[str, ProductEntry] = {}
    by_no: Dict[str, ProductEntry] = {}
    items: List[ProductEntry] = []

    if not _INDEX_PATH.exists():
        return by_id, by_no, items

    with open(_INDEX_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = _parse_line(line)
            by_id[item.product_id] = item
            by_no[item.wsda_reg_no] = item
            items.append(item)

    return by_id, by_no, items


def list_products() -> List[ProductEntry]:
    """Return all products from the index."""
    _, _, items = _load_index()
    return list(items)


def get_product_by_id(product_id: str) -> ProductEntry | None:
    """Return a product record by internal ``product_id``."""
    by_id, _, _ = _load_index()
    return by_id.get(product_id)


def get_product_by_number(number: str) -> ProductEntry | None:
    """Return a product record by WSDA registration number."""
    _, by_no, _ = _load_index()
    return by_no.get(number)


def _match_query(item: ProductEntry, query: str, fields: Iterable[str]) -> bool:
    q = query.lower()
    for field in fields:
        value = getattr(item, field, "")
        if q in str(value).lower():
            return True
    return False


def search_products(query: str, *, fields: Iterable[str] = ("label_name", "brand"), limit: int = 10) -> List[ProductEntry]:
    """Return products matching ``query`` in any of the specified ``fields``."""
    if not query:
        return []
    _, _, items = _load_index()
    matches = [i for i in items if _match_query(i, query, fields)]
    matches.sort(key=lambda x: x.label_name)
    return matches[: max(limit, 0)]

