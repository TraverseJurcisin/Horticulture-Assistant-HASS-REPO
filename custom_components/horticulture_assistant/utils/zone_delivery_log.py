"""Simple in-memory log of irrigation deliveries per zone."""

from dataclasses import dataclass, field, asdict
from typing import Dict, Iterable, Iterator, List, Optional
from datetime import datetime

@dataclass(slots=True)
class DeliveryEvent:
    """Record of a single fertigation or irrigation event."""

    zone_id: str
    plant_ids: List[str]
    batch_id: str
    volume_l: float
    application_method: str
    timestamp: datetime
    delivered_by: Optional[str] = None
    notes: Optional[str] = None

    def as_dict(self) -> Dict[str, object]:
        """Return a serialisable representation of this event."""
        return asdict(self)

@dataclass(slots=True)
class ZoneDeliveryLog:
    """Container tracking all deliveries made to irrigation zones."""

    delivery_events: List[DeliveryEvent] = field(default_factory=list)

    def __iter__(self) -> Iterator[DeliveryEvent]:
        return iter(self.delivery_events)

    def __len__(self) -> int:
        return len(self.delivery_events)

    def log_delivery(
        self,
        zone_id: str,
        plant_ids: Iterable[str],
        batch_id: str,
        volume_l: float,
        application_method: str,
        *,
        delivered_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Add a :class:`DeliveryEvent` entry to the log."""

        event = DeliveryEvent(
            zone_id=zone_id,
            plant_ids=list(plant_ids),
            batch_id=batch_id,
            volume_l=float(volume_l),
            application_method=application_method,
            delivered_by=delivered_by,
            notes=notes,
            timestamp=datetime.utcnow(),
        )
        self.delivery_events.append(event)

    def get_deliveries_for_zone(self, zone_id: str) -> List[DeliveryEvent]:
        """Return all deliveries logged for ``zone_id``."""

        return [e for e in self.delivery_events if e.zone_id == zone_id]

    def get_deliveries_for_plant(self, plant_id: str) -> List[DeliveryEvent]:
        """Return all deliveries that included ``plant_id``."""

        return [e for e in self.delivery_events if plant_id in e.plant_ids]

    def summarize_usage(self) -> Dict[str, float]:
        """Return total volume delivered per zone."""

        summary: Dict[str, float] = {}
        for event in self.delivery_events:
            summary[event.zone_id] = summary.get(event.zone_id, 0.0) + event.volume_l
        return summary
