import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.environ.setdefault(
    "WSDA_INDEX_DIR",
    str(
        ROOT / "custom_components/horticulture_assistant/data/fertilizers/index_sharded"
    ),
)
os.environ.setdefault(
    "WSDA_DETAIL_DIR",
    str(ROOT / "custom_components/horticulture_assistant/data/fertilizers/detail"),
)

from custom_components.horticulture_assistant.utils.wsda_product_index import (
    list_products,
    get_product_by_id,
    get_product_by_number,
    search_products,
)


def test_list_products_has_entries():
    items = list_products()
    assert len(items) > 0
    assert any(i.product_id == "C552F8" for i in items)


def test_lookup_by_id():
    prod = get_product_by_id("C552F8")
    assert prod is not None
    assert prod.k == 60.0


def test_lookup_by_number():
    prod = get_product_by_number("(#2285-0006)")
    assert prod is not None
    assert "POTASH" in prod.label_name


def test_search_products_brand():
    results = search_products("INTREPID", fields=["brand"])
    assert any(p.product_id == "C552F8" for p in results)
