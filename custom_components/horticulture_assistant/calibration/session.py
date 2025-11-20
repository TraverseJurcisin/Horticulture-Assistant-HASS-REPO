from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class LivePoint:
    lux: float
    ppfd: float
    at_utc: str


@dataclass
class CalibrationSession:
    session_id: str
    lux_entity_id: str
    ppfd_entity_id: str | None = None
    model: str = "linear"
    averaging_seconds: int = 3
    notes: str | None = None
    points: list[LivePoint] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
