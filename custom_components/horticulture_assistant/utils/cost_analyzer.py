"""Utilities to track product pricing and summarize costs."""

from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

__all__ = ["ProductPriceEntry", "CostAnalyzer"]


@dataclass(slots=True)
class ProductPriceEntry:
    product_id: str
    distributor: str
    package_size_unit: str  # e.g. 'L', 'kg', 'gal', 'oz'
    package_size: float
    price: float
    date_purchased: datetime
    date_manufactured: Optional[datetime] = None
    expiration_date: Optional[datetime] = None


class CostAnalyzer:
    """Store :class:`ProductPriceEntry` objects and compute cost summaries."""

    def __init__(self) -> None:
        # ``defaultdict`` avoids key checks when adding entries
        self.prices: Dict[str, List[ProductPriceEntry]] = defaultdict(list)

    def add_price_entry(self, entry: ProductPriceEntry) -> None:
        """Record a new :class:`ProductPriceEntry`."""

        self.prices[entry.product_id].append(entry)

    def get_latest_price_per_unit(self, product_id: str) -> Optional[float]:
        """Return the most recent price per package unit for ``product_id``."""

        entries = self.prices.get(product_id)
        if not entries:
            return None
        latest = max(entries, key=lambda e: e.date_purchased)
        return latest.price / latest.package_size

    def summarize_costs(self) -> Dict[str, float]:
        """Return average unit price for each product across all entries."""

        summary: Dict[str, float] = {}
        for product_id, entries in self.prices.items():
            if not entries:
                continue
            unit_prices = [e.price / e.package_size for e in entries]
            summary[product_id] = sum(unit_prices) / len(unit_prices)
        return summary
