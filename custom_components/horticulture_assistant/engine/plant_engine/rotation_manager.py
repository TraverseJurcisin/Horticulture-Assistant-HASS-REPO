from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "companions/rotation_guidance.json"

_DATA: dict[str, dict[str, Any]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_rotation_info",
    "recommended_rotation_years",
    "RotationInfo",
]


@dataclass(slots=True, frozen=True)
class RotationInfo:
    """Rotation guidance for a crop."""

    family: str | None = None
    years: int | None = None


def list_supported_plants() -> list[str]:
    """Return plant types with rotation guidance defined."""
    return list_dataset_entries(_DATA)


def get_rotation_info(plant_type: str) -> RotationInfo:
    """Return :class:`RotationInfo` for ``plant_type``."""
    info = _DATA.get(normalize_key(plant_type), {})
    family = info.get("family")
    years = info.get("years")
    return RotationInfo(
        family=str(family) if family is not None else None,
        years=int(years) if isinstance(years, int | float) else None,
    )


def recommended_rotation_years(plant_type: str) -> int | None:
    """Return recommended years before replanting the same crop."""
    info = get_rotation_info(plant_type)
    return info.years
