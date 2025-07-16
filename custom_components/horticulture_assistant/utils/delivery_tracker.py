from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


BatchDelivery(batch_id: str, delivery_id: str, zone_id: str, volume_delivered_liters: float, delivery_time: datetime.datetime, pH_adjusted: Optional[float] = None, dilution_factor: Optional[float] = None, notes: Optional[str] = None)

DeliveryLog(deliveries: List[__main__.BatchDelivery] = <factory>)
