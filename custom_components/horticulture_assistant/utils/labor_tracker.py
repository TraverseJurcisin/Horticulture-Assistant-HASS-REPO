from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from .json_io import load_json, save_json
from .path_utils import data_path

__all__ = [
    "LaborEntry",
    "LaborLog",
]


@dataclass(slots=True)
class LaborEntry:
    """Single labor activity record."""

    zone_id: str | None
    plant_id: str | None
    task: str
    minutes: float
    timestamp: str
    notes: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class LaborLog:
    """Log and analyze labor activities."""

    def __init__(self, data_file: str | None = None, hass=None) -> None:
        if data_file is None:
            data_file = data_path(hass, "labor_log.json")
        self._data_file = data_file
        self._entries: list[LaborEntry] = []
        try:
            raw = load_json(self._data_file)
            if isinstance(raw, list):
                for item in raw:
                    try:
                        self._entries.append(
                            LaborEntry(
                                zone_id=item.get("zone_id"),
                                plant_id=item.get("plant_id"),
                                task=item["task"],
                                minutes=float(item["minutes"]),
                                timestamp=item["timestamp"],
                                notes=item.get("notes"),
                            )
                        )
                    except Exception:
                        continue
        except FileNotFoundError:
            pass
        except Exception:
            pass

    @property
    def entries(self) -> list[LaborEntry]:
        return list(self._entries)

    def _save(self) -> None:
        save_json(self._data_file, [e.to_dict() for e in self._entries])

    def log_time(
        self,
        task: str,
        minutes: float,
        *,
        zone_id: str | None = None,
        plant_id: str | None = None,
        timestamp: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now()
        entry = LaborEntry(
            zone_id=zone_id,
            plant_id=plant_id,
            task=task,
            minutes=minutes,
            timestamp=timestamp.isoformat(),
            notes=notes,
        )
        self._entries.append(entry)
        self._save()

    def total_minutes(self, *, zone_id: str | None = None, task: str | None = None) -> float:
        total = 0.0
        for e in self._entries:
            if zone_id is not None and e.zone_id != zone_id:
                continue
            if task is not None and e.task != task:
                continue
            total += e.minutes
        return total

    def compute_roi(self, yield_by_zone: dict[str, float]) -> dict[str, float]:
        roi: dict[str, float] = {}
        zones = {e.zone_id for e in self._entries if e.zone_id}
        for zid in zones:
            minutes = self.total_minutes(zone_id=zid)
            hours = minutes / 60.0 if minutes else 0.0
            yield_g = yield_by_zone.get(zid, 0.0)
            roi[zid] = yield_g / hours if hours > 0 else 0.0
        return roi

    def high_effort_low_return(
        self, yield_by_zone: dict[str, float], threshold: float
    ) -> list[str]:
        roi = self.compute_roi(yield_by_zone)
        return [z for z, value in roi.items() if value < threshold]

    def minutes_by_task(self, *, zone_id: str | None = None) -> dict[str, float]:
        """Aggregate labor minutes by task, optionally filtering by zone."""
        totals: dict[str, float] = {}
        for e in self._entries:
            if zone_id is not None and e.zone_id != zone_id:
                continue
            totals[e.task] = totals.get(e.task, 0.0) + e.minutes
        return totals

    def high_effort_tasks(
        self, threshold_minutes: float, *, zone_id: str | None = None
    ) -> list[str]:
        """Return tasks whose logged minutes exceed the threshold."""
        totals = self.minutes_by_task(zone_id=zone_id)
        return [task for task, minutes in totals.items() if minutes > threshold_minutes]
