from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.horticulture_assistant.utils.product_inventory import (
    InventoryRecord,
    ProductInventory,
)


def _record(
    product_id: str,
    batch_id: str,
    quantity: float,
    *,
    days_ago: int,
) -> InventoryRecord:
    now = datetime.now()
    return InventoryRecord(
        product_id=product_id,
        batch_id=batch_id,
        quantity_remaining=quantity,
        unit="L",
        storage_location="warehouse",
        date_received=now - timedelta(days=days_ago),
    )


def test_check_expiring_products_handles_timezone_aware_dates() -> None:
    inventory = ProductInventory()
    record = InventoryRecord(
        product_id="fert-1",
        batch_id="batch-utc",
        quantity_remaining=5.0,
        unit="L",
        storage_location="shed",
        expiration_date=datetime.now(UTC) + timedelta(days=10),
    )
    inventory.add_record(record)

    soon = inventory.check_expiring_products(within_days=30)

    assert record in soon


def test_check_expiring_products_respects_naive_datetimes() -> None:
    inventory = ProductInventory()
    record = InventoryRecord(
        product_id="fert-1",
        batch_id="batch-naive",
        quantity_remaining=5.0,
        unit="L",
        storage_location="shed",
        expiration_date=datetime.now() + timedelta(days=40),
    )
    inventory.add_record(record)

    soon = inventory.check_expiring_products(within_days=30)

    assert record not in soon


def test_consume_product_spans_multiple_batches() -> None:
    inventory = ProductInventory()
    inventory.add_record(_record("nutrient", "batch_a", 5, days_ago=5))
    inventory.add_record(_record("nutrient", "batch_b", 4, days_ago=2))
    inventory.add_record(_record("nutrient", "batch_c", 6, days_ago=0))

    used_batch = inventory.consume_product("nutrient", 8)

    assert used_batch == "batch_a"
    records = inventory.inventory["nutrient"]
    assert records[0].quantity_remaining == 0
    assert records[1].quantity_remaining == 1
    assert records[2].quantity_remaining == 6


def test_consume_product_insufficient_quantity_does_not_mutate() -> None:
    inventory = ProductInventory()
    inventory.add_record(_record("nutrient", "batch_a", 3, days_ago=3))
    inventory.add_record(_record("nutrient", "batch_b", 2, days_ago=1))

    snapshot = [record.quantity_remaining for record in inventory.inventory["nutrient"]]
    used_batch = inventory.consume_product("nutrient", 10)

    assert used_batch is None
    assert [record.quantity_remaining for record in inventory.inventory["nutrient"]] == snapshot
