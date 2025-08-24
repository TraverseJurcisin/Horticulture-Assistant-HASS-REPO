"""Simple fertilizer inventory tracking utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FertilizerListing:
    """External price listing for a fertilizer product."""

    product_id: str
    cost_per_unit: float
    vendor: str | None = None
    unit: str = "g"


@dataclass
class PriceEntry:
    """Historical price information."""

    vendor: str
    unit_price: float
    size: str
    date: datetime = field(default_factory=datetime.now)


@dataclass
class UsageRecord:
    """Record of fertilizer usage."""

    amount_used: float
    unit: str
    zone: str
    date: datetime = field(default_factory=datetime.now)


@dataclass
class FertilizerProduct:
    """Representation of a fertilizer with pricing and usage details."""

    product_id: str
    name: str
    form: str
    unit: str
    derived_from: dict[str, float]
    ph: float | None = None
    ec: float | None = None
    temp_sensitive_ingredients: list[str] = field(default_factory=list)
    expiration: datetime | None = None
    manufactured: datetime | None = None
    price_history: list[PriceEntry] = field(default_factory=list)
    usage_log: list[UsageRecord] = field(default_factory=list)

    def add_price_entry(
        self,
        vendor: str,
        unit_price: float,
        size: str,
        date: datetime | None = None,
    ) -> None:
        entry = PriceEntry(
            vendor=vendor, unit_price=round(unit_price, 2), size=size, date=date or datetime.now()
        )
        self.price_history.append(entry)

    def log_usage(self, amount_used: float, unit: str, zone: str) -> None:
        self.usage_log.append(UsageRecord(amount_used=amount_used, unit=unit, zone=zone))

    def get_latest_price(self) -> PriceEntry | None:
        if not self.price_history:
            return None
        return sorted(self.price_history, key=lambda x: x.date, reverse=True)[0]

    def is_expired(self) -> bool:
        return self.expiration is not None and datetime.now() > self.expiration

    def needs_temp_protection(self, current_temp: float) -> bool:
        return any(current_temp < 5 or current_temp > 30 for _ in self.temp_sensitive_ingredients)

    def average_price_per_unit(self) -> float | None:
        """Return the mean unit price from ``price_history`` if available."""

        if not self.price_history:
            return None
        total = sum(p.unit_price for p in self.price_history)
        return round(total / len(self.price_history), 2)

    def total_usage(self, unit: str | None = None) -> float:
        """Return cumulative amount used optionally filtered by ``unit``."""

        total = 0.0
        for record in self.usage_log:
            if unit is None or record.unit == unit:
                total += record.amount_used
        return round(total, 3)


@dataclass
class FertilizerInventory:
    """Container for :class:`FertilizerProduct` objects."""

    products: dict[str, FertilizerProduct] = field(default_factory=dict)

    def add_product(self, product: FertilizerProduct) -> None:
        self.products[product.product_id] = product

    def get_product(self, product_id: str) -> FertilizerProduct | None:
        return self.products.get(product_id)

    def remove_product(self, product_id: str) -> None:
        self.products.pop(product_id, None)

    def find_by_name(self, name: str) -> list[FertilizerProduct]:
        query = name.lower()
        return [prod for prod in self.products.values() if query in prod.name.lower()]

    def find_expiring_products(self, days_before_expiry: int = 30) -> list[FertilizerProduct]:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            p
            for p in self.products.values()
            if p.expiration and (p.expiration - today).days <= days_before_expiry
        ]


__all__ = [
    "FertilizerListing",
    "PriceEntry",
    "UsageRecord",
    "FertilizerProduct",
    "FertilizerInventory",
]
