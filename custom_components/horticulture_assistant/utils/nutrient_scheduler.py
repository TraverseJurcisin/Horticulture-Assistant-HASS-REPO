"""Generate per-plant nutrient targets based on stage and tags."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, asdict
from functools import lru_cache

try:
    # If running within Home Assistant, this will be available
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None

from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    load_profile,
)
from custom_components.horticulture_assistant.utils.plant_registry import (
    get_plant_type,
)
from plant_engine.nutrient_manager import get_recommended_levels
from plant_engine.utils import load_json, save_json, load_dataset
from custom_components.horticulture_assistant.utils.path_utils import (
    plants_path,
    data_path,
)
from plant_engine.constants import get_stage_multiplier

_LOGGER = logging.getLogger(__name__)

# Map common stage shorthand to formal stage names
STAGE_SYNONYMS = {
    "seed": "seedling",
    "seedling": "seedling",
    "veg": "vegetative",
    "vegetative": "vegetative",
    "flower": "flowering",
    "flowering": "flowering",
    "bloom": "flowering",
    "fruit": "fruiting",
    "fruiting": "fruiting",
}

# Normalize tags to lowercase with underscores for dataset lookups.
def _normalize_tag(tag: str) -> str:
    return str(tag).lower().replace(" ", "_").replace("-", "_")


# Tag-specific nutrient modifiers loaded from a dataset.  Users can extend
# or override this mapping by providing ``nutrient_tag_modifiers.json`` in
# the dataset overlay directory.
TAG_MODIFIER_FILE = "nutrient_tag_modifiers.json"

@lru_cache(maxsize=1)
def _tag_modifiers() -> dict[str, dict[str, float]]:
    """Return normalized tag modifier mapping from the dataset."""
    raw = load_dataset(TAG_MODIFIER_FILE)
    modifiers: dict[str, dict[str, float]] = {}
    for tag, data in raw.items():
        norm_tag = _normalize_tag(tag)
        if not isinstance(data, dict):
            continue
        mods: dict[str, float] = {}
        for nutrient, factor in data.items():
            try:
                mods[nutrient] = float(factor)
            except (TypeError, ValueError):
                continue
        if mods:
            modifiers[norm_tag] = mods
    return modifiers

@dataclass
class NutrientTargets:
    """Structured nutrient targets returned by :func:`schedule_nutrients`."""

    values: dict[str, float]

    def as_dict(self) -> dict[str, float]:
        """Return the targets as a plain dictionary."""
        return asdict(self)["values"]


@lru_cache(maxsize=None)
def _load_profile(plant_id: str, base_dir: str | None) -> dict:
    """Return cached profile data for ``plant_id`` from ``base_dir``."""

    return load_profile(plant_id=plant_id, base_dir=base_dir)


def _profile_dir(hass: HomeAssistant | None) -> str | None:
    """Return profile directory path for ``hass`` or the current working dir."""

    try:
        return plants_path(hass)
    except Exception as exc:  # pragma: no cover
        _LOGGER.warning("Could not determine plants directory: %s", exc)
        return plants_path(None)


def _stage_multiplier(profile: dict, stage_key: str) -> float:
    """Return multiplier for the given stage from profile or defaults."""

    mult = 1.0
    stages = profile.get("stages")
    if isinstance(stages, dict):
        data = stages.get(stage_key) or stages.get(stage_key.lower())
        if isinstance(data, dict):
            for key in ("nutrient_factor", "nutrient_modifier", "nutrient_multiplier"):
                if key in data:
                    try:
                        mult = float(data[key])
                    except (ValueError, TypeError):
                        _LOGGER.warning("Invalid nutrient factor for stage '%s'", stage_key)
                        mult = 1.0
                    break
    if mult == 1.0:
        mult = get_stage_multiplier(stage_key)
    return mult


def _apply_tag_modifiers(targets: dict[str, float], tags: list[str]) -> None:
    """Modify ``targets`` in place using tag multipliers from the dataset."""

    modifiers = _tag_modifiers()
    for tag in tags:
        mods = modifiers.get(_normalize_tag(tag))
        if not mods:
            continue
        for nut, factor in mods.items():
            if nut not in targets:
                continue
            targets[nut] = round(targets[nut] * factor, 2)

def schedule_nutrients(plant_id: str, hass: HomeAssistant = None) -> NutrientTargets:
    """Return adjusted nutrient targets for ``plant_id``.

    Targets are loaded from the plant profile and adjusted using stage
    multipliers and tag-based modifiers. Final values are persisted to
    ``nutrient_targets.json`` for later use.
    """

    base_dir = _profile_dir(hass)
    profile = _load_profile(plant_id, base_dir)
    if not profile:
        _LOGGER.error("Plant profile for '%s' not found or empty", plant_id)
        return NutrientTargets({})

    base_targets = profile.get("nutrients") or {}
    stage = (
        profile.get("general", {}).get("lifecycle_stage")
        or profile.get("general", {}).get("stage")
        or profile.get("stage")
        or "unknown"
    )
    stage_key = STAGE_SYNONYMS.get(str(stage).lower(), str(stage).lower())

    if not base_targets:
        plant_type = (
            str(profile.get("general", {}).get("plant_type"))
            if profile.get("general", {}).get("plant_type")
            else get_plant_type(plant_id, hass)
        )
        if plant_type:
            base_targets = get_recommended_levels(plant_type, stage_key)
            if base_targets:
                _LOGGER.info("Using nutrient guidelines for %s (%s stage)", plant_type, stage_key)
        if not base_targets:
            _LOGGER.warning("No nutrient targets for '%s' and no guidelines found", plant_id)
            return NutrientTargets({})

    mult = _stage_multiplier(profile, stage_key)
    adjusted: dict[str, float] = {}
    for nut, val in base_targets.items():
        try:
            adjusted[nut] = round(float(val) * mult, 2)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid base nutrient value for %s: %s", nut, val)

    tags = [str(t).lower() for t in (profile.get("general", {}).get("tags") or profile.get("tags") or [])]
    _apply_tag_modifiers(adjusted, tags)

    data_dir = data_path(hass)
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "nutrient_targets.json")
    existing = {}
    if os.path.exists(path):
        try:
            existing = load_json(path)
        except Exception:
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing[plant_id] = adjusted
    try:
        save_json(path, existing)
    except Exception as exc:  # pragma: no cover - write errors are unlikely
        _LOGGER.error("Failed to write nutrient targets: %s", exc)

    return NutrientTargets(adjusted)


__all__ = ["schedule_nutrients"]
