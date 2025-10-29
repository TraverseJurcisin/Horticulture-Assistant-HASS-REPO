"""Simple in‑memory product inventory tracking utilities."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta


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
        """Consume ``amount`` of product and return the first batch used.

        When the requested quantity spans multiple batches, the inventory is
        depleted starting with the oldest received stock. The method returns the
        batch identifier of the first batch affected. If the available quantity
        is insufficient or ``amount`` is not positive, ``None`` is returned and
        the inventory remains unchanged.
        """

        if amount <= 0:
            return None

        records = self.inventory.get(product_id)
        if not records:
            return None

        ordered_records = sorted(
            records,
            key=lambda record: record.date_received or datetime.now(),
        )

        total_available = sum(max(0.0, r.quantity_remaining) for r in ordered_records)
        if total_available < amount:
            return None

        remaining = amount
        first_batch: str | None = None
        for record in ordered_records:
            if record.quantity_remaining <= 0:
                continue
            if first_batch is None:
                first_batch = record.batch_id
            allocation = min(record.quantity_remaining, remaining)
            record.quantity_remaining -= allocation
            remaining -= allocation
            if remaining <= 0:
                break

        return first_batch

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


__all__ = ["InventoryRecord", "ProductInventory"]
