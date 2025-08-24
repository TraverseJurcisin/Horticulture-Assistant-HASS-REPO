"""Track fertilizer usage and forecast inventory depletion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .product_inventory import ProductInventory


@dataclass
class UsageEvent:
    """Record of a single fertilizer application."""

    product_id: str
    batch_id: str
    amount: float
    unit: str
    zone: str | None = None
    date: datetime = field(default_factory=datetime.now)


class UsageForecaster:
    """Log fertilizer use and predict when inventory will be depleted."""

    def __init__(self, inventory: ProductInventory) -> None:
        self.inventory = inventory
        self.usage_log: dict[str, list[UsageEvent]] = {}

    def apply_product(
        self,
        product_id: str,
        amount: float,
        unit: str,
        zone: str | None = None,
        date: datetime | None = None,
    ) -> str:
        """Deduct ``amount`` from inventory and log the usage.

        Returns the batch ID that was consumed. Raises ``ValueError`` if
        the inventory does not contain enough product.
        """

        batch_id = self.inventory.consume_product(product_id, amount)
        if batch_id is None:
            raise ValueError(f"Insufficient quantity of {product_id}")

        event = UsageEvent(
            product_id=product_id,
            batch_id=batch_id,
            amount=amount,
            unit=unit,
            zone=zone,
            date=date or datetime.now(),
        )
        self.usage_log.setdefault(product_id, []).append(event)
        return batch_id

    def forecast_runout(self, product_id: str, lookback_days: int = 30) -> float | None:
        """Return estimated days until ``product_id`` is depleted.

        Uses the average daily usage over the last ``lookback_days`` days. If no
        usage is recorded in that period, ``None`` is returned.
        """

        logs = self.usage_log.get(product_id, [])
        if not logs:
            return None

        cutoff = datetime.now() - timedelta(days=lookback_days)
        recent = [e for e in logs if e.date >= cutoff]
        if not recent:
            return None

        first_date = min(e.date for e in recent)
        days_span = max((datetime.now() - first_date).days + 1, 1)
        total_used = sum(e.amount for e in recent)
        avg_daily = total_used / days_span
        if avg_daily <= 0:
            return None

        remaining = self.inventory.get_total_quantity(product_id)
        if remaining <= 0:
            return 0.0
        return round(remaining / avg_daily, 2)


__all__ = ["UsageEvent", "UsageForecaster"]
