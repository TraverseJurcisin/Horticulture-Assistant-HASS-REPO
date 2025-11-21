"""Tests for inventory usage forecasting utilities."""

import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.horticulture_assistant.utils.inventory_usage_forecast import UsageForecaster
from custom_components.horticulture_assistant.utils.product_inventory import InventoryRecord, ProductInventory


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

    aware_date = datetime.now(UTC) - timedelta(days=3)
    naive_date = datetime.now() - timedelta(days=1)

    forecaster.apply_product("fert-1", amount=2.0, unit="L", date=aware_date)
    forecaster.apply_product("fert-1", amount=3.0, unit="L", date=naive_date)

    remaining_days = forecaster.forecast_runout("fert-1", lookback_days=7)

    assert remaining_days is not None
    assert remaining_days > 0
    # The log should contain timezone-aware ``datetime`` objects so that
    # comparisons do not fail when new entries are added later.
    assert all(event.date.tzinfo is not None for event in forecaster.usage_log["fert-1"])


def test_naive_dates_are_localised_before_utc_conversion() -> None:
    if not hasattr(time, "tzset"):
        pytest.skip("time.tzset not available on this platform")

    original_tz = os.environ.get("TZ")
    os.environ["TZ"] = "Etc/GMT+8"
    time.tzset()

    try:
        inventory = _inventory_with_product()
        forecaster = UsageForecaster(inventory)

        naive_local = datetime(2024, 5, 1, 12, 0, 0)
        forecaster.apply_product("fert-1", amount=1.0, unit="L", date=naive_local)

        stored = forecaster.usage_log["fert-1"][0].date
        local_zone = datetime.now().astimezone().tzinfo
        expected = naive_local.replace(tzinfo=local_zone).astimezone(UTC)

        assert stored == expected
    finally:
        if original_tz is not None:
            os.environ["TZ"] = original_tz
        else:
            os.environ.pop("TZ", None)
        time.tzset()
