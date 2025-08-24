"""Light saturation utilities."""

from __future__ import annotations

from .environment_manager import calculate_dli, photoperiod_for_target_dli
from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "light/light_saturation_ppfd.json"

_DATA: dict[str, float] = load_dataset(DATA_FILE)

__all__ = ["list_supported_plants", "get_saturation_ppfd", "recommend_supplemental_hours"]


def list_supported_plants() -> list[str]:
    """Return plant types with saturation data available."""
    return list_dataset_entries(_DATA)


def get_saturation_ppfd(plant_type: str) -> float | None:
    """Return saturation PPFD for ``plant_type`` if defined."""
    val = _DATA.get(normalize_key(plant_type))
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def recommend_supplemental_hours(
    plant_type: str,
    current_ppfd: float,
    photoperiod_hours: float,
) -> float | None:
    """Return additional hours at saturation intensity to reach the target DLI.

    ``current_ppfd`` is the average intensity currently provided over
    ``photoperiod_hours`` hours. If the existing DLI meets or exceeds the
    saturation DLI, ``0.0`` is returned. ``None`` is returned when saturation
    data is missing or inputs are invalid.
    """
    if current_ppfd < 0 or photoperiod_hours <= 0:
        return None

    sat = get_saturation_ppfd(plant_type)
    if sat is None or sat <= 0:
        return None

    target_dli = calculate_dli(sat, photoperiod_hours)
    current_dli = calculate_dli(current_ppfd, photoperiod_hours)
    if current_dli >= target_dli:
        return 0.0

    remaining_dli = target_dli - current_dli
    return photoperiod_for_target_dli(remaining_dli, sat)
