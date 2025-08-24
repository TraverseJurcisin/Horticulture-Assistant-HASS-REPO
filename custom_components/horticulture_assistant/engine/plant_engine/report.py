from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

__all__ = ["DailyReport"]


@dataclass(slots=True)
class DailyReport:
    """Container for daily plant processing results."""

    plant_id: str
    thresholds: dict[str, Any]
    growth: dict[str, Any]
    transpiration: dict[str, Any]
    water_deficit: dict[str, Any]
    rootzone: dict[str, Any]
    nue: dict[str, Any]
    guidelines: dict[str, Any]
    nutrient_targets: dict[str, Any]
    environment_actions: dict[str, Any]
    environment_optimization: dict[str, Any]
    pest_actions: dict[str, Any]
    disease_actions: dict[str, Any]
    lifecycle_stage: str
    stage_info: dict[str, Any]
    tags: list[str]

    def as_dict(self) -> dict[str, Any]:
        """Return the dataclass as a serializable dictionary."""
        return asdict(self)
