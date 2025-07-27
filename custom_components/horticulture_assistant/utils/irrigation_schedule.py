from __future__ import annotations

"""Utilities for parsing irrigation schedule preferences."""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

__all__ = ["Schedule", "parse_schedule"]


@dataclass(slots=True)
class Schedule:
    """Representation of an irrigation schedule."""

    method: str
    time: Optional[str] = None
    duration_min: Optional[float] = None
    volume_l: Optional[float] = None
    target_moisture_pct: Optional[float] = None
    pulses: Optional[Dict[str, List[str]]] = None

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


def parse_schedule(data: Dict[str, object]) -> Schedule:
    """Return :class:`Schedule` parsed from ``data``."""

    method = str(data.get("method")) if data.get("method") else ""
    schedule = Schedule(method=method)
    schedule.time = data.get("time")
    try:
        schedule.duration_min = float(data["duration_min"])
    except Exception:
        pass
    try:
        schedule.volume_l = float(data["volume_l"])
    except Exception:
        pass
    try:
        schedule.target_moisture_pct = float(data["target_moisture_pct"])
    except Exception:
        pass
    pulses = data.get("pulses")
    if isinstance(pulses, dict):
        parsed: Dict[str, List[str]] = {}
        for phase, times in pulses.items():
            if isinstance(times, list):
                parsed[phase] = [str(t) for t in times]
        schedule.pulses = parsed or None
    return schedule

