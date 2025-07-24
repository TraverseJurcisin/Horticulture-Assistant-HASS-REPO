"""Data structures for tracking product pricing over time."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

__all__ = ["ProductPriceEntry", "CostAnalyzer"]


@dataclass
class ProductPriceEntry:
    product_id: str
    distributor: str
    package_size_unit: str  # e.g. 'L', 'kg', 'gal', 'oz'
    package_size: float
    price: float
    date_purchased: datetime
    date_manufactured: Optional[datetime] = None
    expiration_date: Optional[datetime] = None


@dataclass
class CostAnalyzer:
    prices: Dict[str, List[ProductPriceEntry]] = field(default_factory=dict)

    def add_price_entry(self, entry: ProductPriceEntry):
        if entry.product_id not in self.prices:
            self.prices[entry.product_id] = []
        self.prices[entry.product_id].append(entry)

    def get_latest_price_per_unit(self, product_id: str) -> Optional[float]:
        if product_id not in self.prices or not self.prices[product_id]:
            return None
        latest = sorted(self.prices[product_id], key=lambda e: e.date_purchased)[-1]
        return latest.price / latest.package_size

    def summarize_costs(self) -> Dict[str, float]:
        summary = {}
        for product_id, entries in self.prices.items():
            if entries:
                unit_prices = [e.price / e.package_size for e in entries]
                summary[product_id] = sum(unit_prices) / len(unit_prices)
        return summary

