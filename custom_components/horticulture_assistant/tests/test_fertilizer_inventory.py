from datetime import datetime, timedelta

from custom_components.horticulture_assistant.utils.fertilizer_inventory import (
    FertilizerProduct,
    FertilizerInventory,
)


def test_inventory_basic_operations():
    product = FertilizerProduct(
        product_id="grow",
        name="Grow",
        form="liquid",
        unit="L",
        derived_from={"N": 0.05},
        expiration=datetime.now() + timedelta(days=10),
    )
    inv = FertilizerInventory()
    inv.add_product(product)

    assert inv.get_product("grow") is product
    assert inv.find_by_name("grow") == [product]
    assert inv.find_expiring_products() == [product]

    inv.remove_product("grow")
    assert inv.get_product("grow") is None


def test_product_price_and_usage():
    product = FertilizerProduct(
        product_id="test",
        name="Test",
        form="solid",
        unit="g",
        derived_from={},
    )
    product.add_price_entry("A", 1.0, "1kg")
    product.add_price_entry("B", 2.0, "1kg")
    latest = product.get_latest_price()
    assert latest.vendor == "B"
    assert product.average_price_per_unit() == 1.5

    product.log_usage(100, "g", "GH1")
    product.log_usage(50, "g", "GH1")
    assert len(product.usage_log) == 2
    assert not product.is_expired()
    assert product.total_usage() == 150


