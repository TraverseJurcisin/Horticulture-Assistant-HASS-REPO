from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

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


def test_consume_product_spans_multiple_batches() -> None:
    inventory = ProductInventory()
    first = InventoryRecord(
        product_id="fert-2",
        batch_id="batch-a",
        quantity_remaining=25.0,
        unit="L",
        storage_location="shed",
        date_received=datetime(2024, 1, 1),
    )
    second = InventoryRecord(
        product_id="fert-2",
        batch_id="batch-b",
        quantity_remaining=10.0,
        unit="L",
        storage_location="shed",
        date_received=datetime(2024, 1, 5),
    )
    third = InventoryRecord(
        product_id="fert-2",
        batch_id="batch-c",
        quantity_remaining=20.0,
        unit="L",
        storage_location="shed",
        date_received=datetime(2024, 1, 10),
    )
    inventory.add_record(first)
    inventory.add_record(second)
    inventory.add_record(third)

    batch = inventory.consume_product("fert-2", 40.0)

    assert batch == "batch-a"
    assert first.quantity_remaining == 0.0
    assert second.quantity_remaining == 0.0
    assert third.quantity_remaining == 15.0


def test_consume_product_reverts_when_insufficient_stock() -> None:
    inventory = ProductInventory()
    first = InventoryRecord(
        product_id="fert-3",
        batch_id="batch-a",
        quantity_remaining=5.0,
        unit="kg",
        storage_location="warehouse",
    )
    second = InventoryRecord(
        product_id="fert-3",
        batch_id="batch-b",
        quantity_remaining=4.0,
        unit="kg",
        storage_location="warehouse",
    )
    inventory.add_record(first)
    inventory.add_record(second)

    result = inventory.consume_product("fert-3", 20.0)

    assert result is None
    assert first.quantity_remaining == pytest.approx(5.0)
    assert second.quantity_remaining == pytest.approx(4.0)
