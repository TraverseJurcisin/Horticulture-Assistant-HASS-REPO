from dataclasses import dataclass, field
from typing import List, Optional
import datetime

@dataclass(slots=True)
class BatchDelivery:
    batch_id: str
    delivery_id: str
    zone_id: str
    volume_delivered_liters: float
    delivery_time: datetime.datetime
    pH_adjusted: Optional[float] = None
    dilution_factor: Optional[float] = None
    notes: Optional[str] = None

@dataclass(slots=True)
class DeliveryLog:
    deliveries: List[BatchDelivery] = field(default_factory=list)
