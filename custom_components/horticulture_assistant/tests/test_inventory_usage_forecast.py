from datetime import datetime, timedelta

from ..utils.inventory_usage_forecast import UsageForecaster
from ..utils.product_inventory import InventoryRecord, ProductInventory


def test_usage_logging_and_forecast():
    inv = ProductInventory()
    rec1 = InventoryRecord(
        product_id="grow",
        batch_id="b1",
        quantity_remaining=100.0,
        unit="g",
        storage_location="shed",
    )
    rec2 = InventoryRecord(
        product_id="grow",
        batch_id="b2",
        quantity_remaining=100.0,
        unit="g",
        storage_location="shed",
    )
    inv.add_record(rec1)
    inv.add_record(rec2)

    forecaster = UsageForecaster(inv)

    forecaster.apply_product(
        "grow",
        30.0,
        "g",
        zone="zone1",
        date=datetime.now() - timedelta(days=2),
    )
    forecaster.apply_product(
        "grow",
        30.0,
        "g",
        zone="zone1",
        date=datetime.now() - timedelta(days=1),
    )
    forecaster.apply_product("grow", 20.0, "g", zone="zone1")

    assert len(forecaster.usage_log["grow"]) == 3
    assert inv.get_total_quantity("grow") == 120.0

    days = forecaster.forecast_runout("grow")
    assert days and 4.0 < days < 5.0


def test_forecast_no_usage():
    inv = ProductInventory()
    inv.add_record(
        InventoryRecord(
            product_id="f",
            batch_id="b",
            quantity_remaining=10.0,
            unit="g",
            storage_location="shed",
        )
    )
    forecaster = UsageForecaster(inv)
    assert forecaster.forecast_runout("f") is None
