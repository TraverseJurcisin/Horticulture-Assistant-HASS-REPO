from __future__ import annotations

"""Utilities for parsing irrigation schedule preferences.

The module exposes a small :class:`Schedule` dataclass used to represent an
irrigation schedule.  ``Schedule.from_dict`` converts the loosely-typed mapping
stored in plant profiles into a structured object.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Mapping, Optional

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

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Schedule":
        """Create an instance from a generic mapping."""

        def _to_float(val: object) -> Optional[float]:
            try:
                return float(val)  # type: ignore[arg-type]
            except Exception:
                return None

        method = str(data.get("method", ""))
        sched = cls(method=method)
        sched.time = data.get("time") if data.get("time") else None
        sched.duration_min = _to_float(data.get("duration_min"))
        sched.volume_l = _to_float(data.get("volume_l"))
        sched.target_moisture_pct = _to_float(data.get("target_moisture_pct"))

        pulses = data.get("pulses")
        if isinstance(pulses, Mapping):
            parsed: Dict[str, List[str]] = {
                phase: [str(t) for t in times]
                for phase, times in pulses.items()
                if isinstance(times, Iterable)
            }
            sched.pulses = parsed or None

        return sched


def parse_schedule(data: Mapping[str, object]) -> Schedule:
    """Return :class:`Schedule` parsed from ``data``."""

    return Schedule.from_dict(data)
