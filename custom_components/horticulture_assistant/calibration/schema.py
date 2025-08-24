from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CalibrationPoint:
    lux: float
    ppfd: float  # µmol m^-2 s^-1
    at_utc: str  # ISO8601


@dataclass
class CalibrationModel:
    model: str  # "linear" | "quadratic" | "power"
    coefficients: list[float]  # linear: [a,b] -> ppfd = a*lux + b
    r2: float
    rmse: float
    n: int
    lux_min: float
    lux_max: float
    notes: str | None = None


@dataclass
class CalibrationRecord:
    lux_entity_id: str
    device_id: str | None
    model: CalibrationModel
    points: list[CalibrationPoint]

    def to_json(self) -> dict[str, Any]:
        return {
            "lux_entity_id": self.lux_entity_id,
            "device_id": self.device_id,
            "model": asdict(self.model),
            "points": [asdict(p) for p in self.points],
        }
