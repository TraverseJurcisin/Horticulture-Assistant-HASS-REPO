"""Generate per-plant nutrient targets based on stage and tags."""

from __future__ import annotations

import json
import os
import logging
from dataclasses import dataclass, asdict

try:
    # If running within Home Assistant, this will be available
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None

from custom_components.horticulture_assistant.utils.plant_profile_loader import load_profile
from plant_engine.nutrient_manager import get_recommended_levels
from plant_engine.utils import load_json, save_json

_LOGGER = logging.getLogger(__name__)

# Default multipliers for nutrient targets by lifecycle stage
STAGE_MULTIPLIERS = {
    "seedling": 0.5,
    "vegetative": 1.0,
    "flowering": 1.2,
    "fruiting": 1.1,
}

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

# Tag-specific nutrient modifiers (multipliers for specific nutrients)
TAG_NUTRIENT_MODIFIERS = {
    "high-nitrogen": {"N": 1.2},
    "low-nitrogen": {"N": 0.8},
    "high_nitrogen": {"N": 1.2},       # allow underscore variants
    "low_nitrogen": {"N": 0.8},
    "potassium-sensitive": {"K": 0.8},
    "potassium_sensitive": {"K": 0.8},
    "high-potassium": {"K": 1.2},
    "high_potassium": {"K": 1.2},
    "low-potassium": {"K": 0.9},
    "low_potassium": {"K": 0.9},
}

PLANT_REGISTRY_FILE = "plant_registry.json"


@dataclass
class NutrientTargets:
    """Structured nutrient targets returned by :func:`schedule_nutrients`."""

    values: dict[str, float]

    def as_dict(self) -> dict[str, float]:
        """Return the targets as a plain dictionary."""
        return asdict(self)["values"]


def _get_plant_type(plant_id: str, profile: dict, hass: HomeAssistant | None) -> str | None:
    """Return plant type for ``plant_id`` from profile or registry."""
    plant_type = profile.get("general", {}).get("plant_type")
    if plant_type:
        return str(plant_type).lower()

    reg_path = hass.config.path(PLANT_REGISTRY_FILE) if hass else PLANT_REGISTRY_FILE
    try:
        data = load_json(reg_path)
        plant_type = data.get(plant_id, {}).get("plant_type")
        if plant_type:
            return str(plant_type).lower()
    except Exception:
        pass
    return None


def _load_profile(plant_id: str, hass: HomeAssistant | None) -> dict:
    """Return loaded profile for ``plant_id`` using Home Assistant if provided."""

    base_dir = None
    if hass is not None:
        try:
            base_dir = hass.config.path("plants")
        except Exception as exc:  # pragma: no cover - HA may not provide path
            _LOGGER.warning("Could not determine plants directory: %s", exc)
            base_dir = None
    return load_profile(plant_id=plant_id, base_dir=base_dir)


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
        mult = STAGE_MULTIPLIERS.get(stage_key, 1.0)
    return mult


def _apply_tag_modifiers(targets: dict[str, float], tags: list[str]) -> None:
    """Modify ``targets`` in place using tag multipliers."""

    for tag in tags:
        mods = TAG_NUTRIENT_MODIFIERS.get(tag)
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

    profile = _load_profile(plant_id, hass)
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
        plant_type = _get_plant_type(plant_id, profile, hass)
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

    data_dir = hass.config.path("data") if hass else os.path.join(os.getcwd(), "data")
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
