import datetime
from dataclasses import dataclass, field


@dataclass(slots=True)
class BatchDelivery:
    batch_id: str
    delivery_id: str
    zone_id: str
    volume_delivered_liters: float
    delivery_time: datetime.datetime
    pH_adjusted: float | None = None
    dilution_factor: float | None = None
    notes: str | None = None


@dataclass(slots=True)
class DeliveryLog:
    deliveries: list[BatchDelivery] = field(default_factory=list)
