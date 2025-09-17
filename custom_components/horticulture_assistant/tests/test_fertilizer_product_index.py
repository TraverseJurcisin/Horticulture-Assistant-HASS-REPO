import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("FERTILIZER_DATASET_INDEX_DIR", str(ROOT / "feature/fertilizer_dataset_sharded/index_sharded"))
os.environ.setdefault("FERTILIZER_DATASET_DETAIL_DIR", str(ROOT / "feature/fertilizer_dataset_sharded/detail"))

from custom_components.horticulture_assistant.utils.fertilizer_product_index import (  # noqa: E402
    get_product_by_id,
    get_product_by_number,
    list_products,
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
