from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class DeliveryEvent:
    zone_id: str
    plant_ids: List[str]
    batch_id: str
    volume_l: float
    application_method: str
    timestamp: datetime
    delivered_by: Optional[str] = None
    notes: Optional[str] = None

@dataclass
class ZoneDeliveryLog:
    delivery_events: List[DeliveryEvent] = field(default_factory=list)

    def log_delivery(self, zone_id: str, plant_ids: List[str], batch_id: str,
                     volume_l: float, application_method: str,
                     delivered_by: Optional[str] = None, notes: Optional[str] = None):
        event = DeliveryEvent(
            zone_id=zone_id,
            plant_ids=plant_ids,
            batch_id=batch_id,
            volume_l=volume_l,
            application_method=application_method,
            delivered_by=delivered_by,
            notes=notes,
            timestamp=datetime.now()
        )
        self.delivery_events.append(event)

    def get_deliveries_for_zone(self, zone_id: str) -> List[DeliveryEvent]:
        return [e for e in self.delivery_events if e.zone_id == zone_id]

    def get_deliveries_for_plant(self, plant_id: str) -> List[DeliveryEvent]:
        return [e for e in self.delivery_events if plant_id in e.plant_ids]

    def summarize_usage(self) -> Dict[str, float]:
        summary = {}
        for event in self.delivery_events:
            summary[event.zone_id] = summary.get(event.zone_id, 0.0) + event.volume_l
        return summary
