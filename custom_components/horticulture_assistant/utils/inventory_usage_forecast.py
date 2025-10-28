"""Track fertilizer usage and forecast inventory depletion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .product_inventory import ProductInventory


def _utcnow() -> datetime:
    """Return a timezone-aware ``datetime`` in UTC."""

    return datetime.now(timezone.utc)


def _ensure_utc(dt: datetime | None) -> datetime:
    """Return a timezone-aware UTC ``datetime`` for ``dt``.

    ``datetime`` values stored in the usage log may come from different sources
    (for example Home Assistant events or manually provided values) and can be
    either naive or timezone-aware. Python raises ``TypeError`` when comparing a
    naive ``datetime`` to an aware one, which caused ``forecast_runout`` to
    crash if a caller supplied an aware ``datetime``. Normalising to UTC keeps
    the comparisons safe while preserving ordering semantics.
    """

    if dt is None:
        return _utcnow()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class UsageEvent:
    """Record of a single fertilizer application."""

    product_id: str
    batch_id: str
    amount: float
    unit: str
    zone: str | None = None
    date: datetime = field(default_factory=_utcnow)


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
            date=_ensure_utc(date),
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

        now = _ensure_utc(None)
        cutoff = now - timedelta(days=lookback_days)
        recent = [e for e in logs if _ensure_utc(e.date) >= cutoff]
        if not recent:
            return None

        first_date = min(_ensure_utc(e.date) for e in recent)
        elapsed_days = (now - first_date).total_seconds() / 86400
        days_span = max(elapsed_days, 1.0)
        total_used = sum(e.amount for e in recent)
        avg_daily = total_used / days_span
        if avg_daily <= 0:
            return None

        remaining = self.inventory.get_total_quantity(product_id)
        if remaining <= 0:
            return 0.0
        return round(remaining / avg_daily, 2)


__all__ = ["UsageEvent", "UsageForecaster"]
