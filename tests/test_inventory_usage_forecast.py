"""Tests for inventory usage forecasting utilities."""

from datetime import datetime, timedelta, timezone

from custom_components.horticulture_assistant.utils.inventory_usage_forecast import (
    UsageForecaster,
)
from custom_components.horticulture_assistant.utils.product_inventory import (
    InventoryRecord,
    ProductInventory,
)


def _inventory_with_product(quantity: float = 20.0) -> ProductInventory:
    inventory = ProductInventory()
    inventory.add_record(
        InventoryRecord(
            product_id="fert-1",
            batch_id="batch-001",
            quantity_remaining=quantity,
            unit="L",
            storage_location="shed",
        )
    )
    return inventory


def test_forecast_runout_handles_timezone_aware_usage_dates() -> None:
    inventory = _inventory_with_product()
    forecaster = UsageForecaster(inventory)

    aware_date = datetime.now(timezone.utc) - timedelta(days=3)
    naive_date = datetime.now() - timedelta(days=1)

    forecaster.apply_product("fert-1", amount=2.0, unit="L", date=aware_date)
    forecaster.apply_product("fert-1", amount=3.0, unit="L", date=naive_date)

    remaining_days = forecaster.forecast_runout("fert-1", lookback_days=7)

    assert remaining_days is not None
    assert remaining_days > 0
    # The log should contain timezone-aware ``datetime`` objects so that
    # comparisons do not fail when new entries are added later.
    assert all(event.date.tzinfo is not None for event in forecaster.usage_log["fert-1"])
