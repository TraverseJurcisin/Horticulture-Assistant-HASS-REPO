"""Simple in‑memory product inventory tracking utilities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class InventoryRecord:
    """Metadata for a specific batch of a product."""

    product_id: str
    batch_id: str
    quantity_remaining: float
    unit: str
    storage_location: str
    expiration_date: Optional[datetime] = None
    date_received: Optional[datetime] = None
    date_manufactured: Optional[datetime] = None
    temperature_sensitive: bool = False
    critical_temperature_c: Optional[float] = None
    is_biological: bool = False


@dataclass
class ProductInventory:
    """Container for tracked inventory records."""

    inventory: Dict[str, List[InventoryRecord]] = field(default_factory=dict)

    def add_record(self, record: InventoryRecord) -> None:
        """Add a new :class:`InventoryRecord` to the inventory."""

        if record.product_id not in self.inventory:
            self.inventory[record.product_id] = []
        self.inventory[record.product_id].append(record)

    def consume_product(self, product_id: str, amount: float) -> Optional[str]:
        """Consume ``amount`` of product and return the batch used."""

        if product_id not in self.inventory:
            return None
        for record in sorted(
            self.inventory[product_id],
            key=lambda x: x.date_received or datetime.now(),
        ):
            if record.quantity_remaining >= amount:
                record.quantity_remaining -= amount
                return record.batch_id
        return None

    def get_total_quantity(self, product_id: str) -> float:
        """Return total remaining quantity for ``product_id``."""

        if product_id not in self.inventory:
            return 0.0
        return sum(r.quantity_remaining for r in self.inventory[product_id])

    def check_expiring_products(self, within_days: int = 30) -> List[InventoryRecord]:
        """Return records with an expiration date within ``within_days``."""

        soon: List[InventoryRecord] = []
        now = datetime.now()
        for records in self.inventory.values():
            for r in records:
                if r.expiration_date and (r.expiration_date - now).days <= within_days:
                    soon.append(r)
        return soon


__all__ = ["InventoryRecord", "ProductInventory"]
