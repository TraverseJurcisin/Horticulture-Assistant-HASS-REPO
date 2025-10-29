"""Simple in‑memory product inventory tracking utilities."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class InventoryRecord:
    """Metadata for a specific batch of a product."""

    product_id: str
    batch_id: str
    quantity_remaining: float
    unit: str
    storage_location: str
    expiration_date: datetime | None = None
    date_received: datetime | None = None
    date_manufactured: datetime | None = None
    temperature_sensitive: bool = False
    critical_temperature_c: float | None = None
    is_biological: bool = False


@dataclass
class ProductInventory:
    """Container for tracked inventory records."""

    inventory: dict[str, list[InventoryRecord]] = field(default_factory=dict)

    def add_record(self, record: InventoryRecord) -> None:
        """Add a new :class:`InventoryRecord` to the inventory."""

        if record.product_id not in self.inventory:
            self.inventory[record.product_id] = []
        self.inventory[record.product_id].append(record)

    def consume_product(self, product_id: str, amount: float) -> str | None:
        """Consume ``amount`` of product and return the batch used."""

        if product_id not in self.inventory:
            return None
        for record in sorted(self.inventory[product_id], key=_record_sort_key):
            if record.quantity_remaining >= amount:
                record.quantity_remaining -= amount
                return record.batch_id
        return None

    def get_total_quantity(self, product_id: str) -> float:
        """Return total remaining quantity for ``product_id``."""

        if product_id not in self.inventory:
            return 0.0
        return sum(r.quantity_remaining for r in self.inventory[product_id])

    def check_expiring_products(self, within_days: int = 30) -> list[InventoryRecord]:
        """Return records with an expiration date within ``within_days``."""

        soon: list[InventoryRecord] = []
        default_now = datetime.now()
        window = timedelta(days=within_days)
        for records in self.inventory.values():
            for r in records:
                expiry = r.expiration_date
                if expiry is None:
                    continue

                reference_now = default_now if expiry.tzinfo is None else datetime.now(expiry.tzinfo)
                if expiry <= reference_now + window:
                    soon.append(r)
        return soon


def _record_sort_key(record: InventoryRecord) -> tuple[int, datetime]:
    """Return a deterministic sort key handling timezone-aware datetimes."""

    received = record.date_received
    if received is None:
        # Place undated batches last while keeping ordering stable.
        return (1, datetime.min.replace(tzinfo=timezone.utc))

    if received.tzinfo is None:
        normalised = received.replace(tzinfo=timezone.utc)
    else:
        normalised = received.astimezone(timezone.utc)

    return (0, normalised)


__all__ = ["InventoryRecord", "ProductInventory"]
