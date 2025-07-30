import datetime
from custom_components.horticulture_assistant.utils.product_inventory import (
    ProductInventory, InventoryRecord,
)
from custom_components.horticulture_assistant.utils.product_storage_monitor import (
    ProductStorageMonitor,
)
from custom_components.horticulture_assistant.utils.product_usage_logger import (
    log_product_usage,
)
from custom_components.horticulture_assistant.utils.product_tracker import (
    ProductTracker, ProductInstance,
)


def test_inventory_basic_consumption():
    inv = ProductInventory()
    rec1 = InventoryRecord(
        product_id="fert1",
        batch_id="b1",
        quantity_remaining=5.0,
        unit="L",
        storage_location="shed",
        date_received=datetime.datetime(2024, 1, 1),
    )
    rec2 = InventoryRecord(
        product_id="fert1",
        batch_id="b2",
        quantity_remaining=3.0,
        unit="L",
        storage_location="shed",
        date_received=datetime.datetime(2024, 2, 1),
    )
    inv.add_record(rec1)
    inv.add_record(rec2)

    batch = inv.consume_product("fert1", 2.0)
    assert batch == "b1"
    assert rec1.quantity_remaining == 3.0
    assert inv.get_total_quantity("fert1") == 6.0


def test_inventory_check_expiring():
    inv = ProductInventory()
    soon = datetime.datetime.now() + datetime.timedelta(days=10)
    rec = InventoryRecord(
        product_id="fert",
        batch_id="b",
        quantity_remaining=1.0,
        unit="kg",
        storage_location="shed",
        expiration_date=soon,
    )
    inv.add_record(rec)
    assert inv.check_expiring_products(within_days=15) == [rec]


def test_storage_monitor_helpers():
    assert not ProductStorageMonitor.is_expired(None)
    old_date = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    assert ProductStorageMonitor.is_expired(old_date)

    profile = {"Salt": {"precip_temp": 5.0}}
    warn = ProductStorageMonitor.flag_temperature_risk(0.0, profile)
    assert "Salt" in warn

    mfg = (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%Y-%m-%d")
    assert ProductStorageMonitor.check_manufacturing_date(mfg, 12)


def test_usage_logger_and_tracker():
    record = log_product_usage("p", "b", ["zone"], 1.2345, recipe_id="r")
    assert record["volume_liters"] == 1.2345
    tracker = ProductTracker()
    inst = ProductInstance(
        product_name="Grow",
        vendor="A",
        size=1.0,
        size_unit="L",
        cost=10.0,
        purchase_date="2024-01-01",
        expiration_date=(datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
    )
    tracker.add_product(inst)
    assert tracker.total_available("Grow", "L") == 1.0
    assert tracker.get_product_by_vendor("Grow", "A") == [inst]
    assert "Grow" in tracker.export_json()
