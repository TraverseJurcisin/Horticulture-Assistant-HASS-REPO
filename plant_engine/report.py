from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

__all__ = ["DailyReport"]

@dataclass
class DailyReport:
    """Container for daily plant processing results."""

    plant_id: str
    thresholds: Dict[str, Any]
    growth: Dict[str, Any]
    transpiration: Dict[str, Any]
    water_deficit: Dict[str, Any]
    rootzone: Dict[str, Any]
    nue: Dict[str, Any]
    guidelines: Dict[str, Any]
    nutrient_targets: Dict[str, Any]
    environment_actions: Dict[str, Any]
    environment_optimization: Dict[str, Any]
    pest_actions: Dict[str, Any]
    disease_actions: Dict[str, Any]
    lifecycle_stage: str
    stage_info: Dict[str, Any]
    tags: List[str]

    def as_dict(self) -> Dict[str, Any]:
        """Return the dataclass as a serializable dictionary."""
        return asdict(self)
