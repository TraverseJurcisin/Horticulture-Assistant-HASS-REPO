"""Stage-based light intensity recommendations."""

from __future__ import annotations

from functools import cache

from ..engine.plant_engine.utils import load_dataset, normalize_key

DATA_FILE = "stages/stage_light_requirements.json"


@cache
def get_stage_light(plant_type: str, stage: str) -> float | None:
    """Return recommended PPFD for ``plant_type`` and ``stage``.

    Values are looked up in :data:`DATA_FILE`. ``None`` is returned when
    no entry exists or the value cannot be interpreted as a float.
    """
    data = load_dataset(DATA_FILE)
    plant = data.get(normalize_key(plant_type))
    if isinstance(plant, dict):
        value = plant.get(normalize_key(stage))
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    return None


@cache
def generate_light_schedule(plant_type: str) -> dict[str, float]:
    """Return stage to PPFD mapping for ``plant_type``."""
    data = load_dataset(DATA_FILE)
    plant = data.get(normalize_key(plant_type))
    result: dict[str, float] = {}
    if isinstance(plant, dict):
        for stage, value in plant.items():
            try:
                result[stage] = float(value)
            except (TypeError, ValueError):
                continue
    return result


__all__ = ["get_stage_light", "generate_light_schedule"]
