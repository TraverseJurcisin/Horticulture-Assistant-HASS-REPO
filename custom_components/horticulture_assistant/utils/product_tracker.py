"""Minimal inventory tracker for fertilizer products."""

import datetime
import json
from dataclasses import dataclass, field


@dataclass
class ProductInstance:
    """Single product container used by :class:`ProductTracker`."""

    product_name: str
    vendor: str
    size: float
    size_unit: str
    cost: float
    purchase_date: str
    manufacture_date: str | None = None
    expiration_date: str | None = None
    temperature_sensitive: bool = False
    mineral_based: bool = True
    ec: float | None = None
    ph: float | None = None
    concentration_note: str | None = None
    derived_from: list[str] = field(default_factory=list)


class ProductTracker:
    """Simple manager for a collection of :class:`ProductInstance`."""

    def __init__(self) -> None:
        self.inventory: list[ProductInstance] = []

    def add_product(self, instance: ProductInstance) -> None:
        """Add a :class:`ProductInstance` to the tracker."""

        self.inventory.append(instance)

    def get_valid_products(
        self, product_name: str, as_of_date: str | None = None
    ) -> list[ProductInstance]:
        if as_of_date is None:
            as_of_date = datetime.date.today().isoformat()

        def is_valid(prod: ProductInstance) -> bool:
            if not prod.expiration_date or prod.mineral_based:
                return True
            return prod.expiration_date > as_of_date

        return [p for p in self.inventory if p.product_name == product_name and is_valid(p)]

    def total_available(self, product_name: str, unit: str) -> float:
        valid = self.get_valid_products(product_name)
        return sum(p.size for p in valid if p.size_unit == unit)

    def get_product_by_vendor(self, product_name: str, vendor: str) -> list[ProductInstance]:
        return [p for p in self.inventory if p.product_name == product_name and p.vendor == vendor]

    def export_json(self) -> str:
        """Return the tracker contents as a JSON string."""

        return json.dumps([p.__dict__ for p in self.inventory], indent=2)


__all__ = ["ProductInstance", "ProductTracker"]
