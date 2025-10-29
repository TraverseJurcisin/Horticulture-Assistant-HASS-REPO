from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.horticulture_assistant.utils.product_inventory import (
    InventoryRecord,
    ProductInventory,
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


def test_consume_product_handles_mixed_timezone_dates() -> None:
    inventory = ProductInventory()
    aware_record = InventoryRecord(
        product_id="fert-1",
        batch_id="batch-aware",
        quantity_remaining=5.0,
        unit="L",
        storage_location="shed",
        date_received=datetime.now(UTC) - timedelta(days=1),
    )
    naive_record = InventoryRecord(
        product_id="fert-1",
        batch_id="batch-naive",
        quantity_remaining=5.0,
        unit="L",
        storage_location="shed",
        date_received=datetime.now() - timedelta(days=2),
    )
    undated_record = InventoryRecord(
        product_id="fert-1",
        batch_id="batch-undated",
        quantity_remaining=5.0,
        unit="L",
        storage_location="shed",
        date_received=None,
    )

    inventory.add_record(undated_record)
    inventory.add_record(aware_record)
    inventory.add_record(naive_record)

    first_batch = inventory.consume_product("fert-1", 1.0)

    assert first_batch == "batch-naive"
    assert naive_record.quantity_remaining == 4.0
