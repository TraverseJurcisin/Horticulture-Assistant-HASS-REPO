"""Utility to generate per-plant nutrient targets."""

from __future__ import annotations

import json
import os
import logging

try:
    # If running within Home Assistant, this will be available
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None

from custom_components.horticulture_assistant.utils.plant_profile_loader import load_profile
from plant_engine.nutrient_manager import get_recommended_levels
from plant_engine.stage_factors import get_stage_factor
from plant_engine.utils import load_json

_LOGGER = logging.getLogger(__name__)

# Stage nutrient multipliers now loaded from dataset

# Map common stage shorthand to formal stage names
STAGE_SYNONYMS = {
    "seed": "seedling",
    "seedling": "seedling",
    "veg": "vegetative",
    "vegetative": "vegetative",
    "flower": "flowering",
    "flowering": "flowering",
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

def schedule_nutrients(plant_id: str, hass: HomeAssistant = None) -> dict:
    """
    Adjust nutrient targets for a given plant based on its lifecycle stage and tags.
    
    Loads the plant's profile (JSON/YAML) and applies adjustments:
      - Stage-based multiplier (e.g., lower nutrients for seedling, higher for flowering).
      - Tag-specific modifiers (e.g., increase N for "high-nitrogen" tag).
    
    The base nutrient targets are taken from the profile's "nutrients" section.
    Adjusted targets are saved to data/nutrient_targets.json and returned as a dict.
    Logging is performed for each adjustment and any missing data.
    """
    # Determine profile directory and load profile
    base_dir = None
    if hass is not None:
        try:
            base_dir = hass.config.path("plants")
        except Exception as e:
            _LOGGER.warning("Could not determine plants directory from Home Assistant: %s", e)
            base_dir = None
    profile = load_profile(plant_id=plant_id, base_dir=base_dir)
    if not profile:
        _LOGGER.error("Plant profile for '%s' not found or empty. Cannot schedule nutrients.", plant_id)
        return {}
    # Get base nutrient targets from profile
    base_targets = profile.get("nutrients") or {}
    stage = (
        profile.get("general", {}).get("lifecycle_stage")
        or profile.get("general", {}).get("stage")
        or profile.get("stage")
        or "unknown"
    )
    stage_str = str(stage).lower()
    stage_key = STAGE_SYNONYMS.get(stage_str, stage_str)

    if not base_targets:
        plant_type = _get_plant_type(plant_id, profile, hass)
        if plant_type:
            base_targets = get_recommended_levels(plant_type, stage_key)
            if base_targets:
                _LOGGER.info(
                    "Using nutrient guidelines for %s (%s stage)",
                    plant_type,
                    stage_key,
                )
        if not base_targets:
            _LOGGER.warning(
                "No nutrient targets for plant '%s' and no guidelines found. Skipping.",
                plant_id,
            )
            return {}
    # Determine stage multiplier
    stage_multiplier = 1.0
    stage_data = {}
    if isinstance(profile.get("stages"), dict):
        stage_data = profile["stages"].get(stage_key) or profile["stages"].get(stage_str) or {}
        if isinstance(stage_data, dict):
            # Check for a stage-specific nutrient factor in profile
            for key in ("nutrient_factor", "nutrient_modifier", "nutrient_multiplier"):
                if key in stage_data:
                    try:
                        stage_multiplier = float(stage_data[key])
                        _LOGGER.info("Profile-defined nutrient factor for stage '%s': %sx", stage_key, stage_multiplier)
                    except (ValueError, TypeError):
                        stage_multiplier = 1.0
                        _LOGGER.warning("Invalid nutrient factor in profile for stage '%s'; defaulting to 1.0", stage_key)
                    break
    if stage_multiplier == 1.0:
        stage_multiplier = get_stage_factor(stage_key)
        if stage_multiplier == 1.0 and stage_key not in ("unknown", ""):
            _LOGGER.info("No predefined nutrient multiplier for stage '%s'; using 1.0", stage_key)
    # Log stage-based adjustment
    if stage_multiplier != 1.0:
        _LOGGER.info("Applying stage multiplier for '%s': %sx to all nutrient targets", stage_key, stage_multiplier)
    else:
        if stage_key in ("unknown", ""):
            _LOGGER.info("Lifecycle stage for plant '%s' is unknown; no stage-based adjustments applied.", plant_id)
        else:
            _LOGGER.debug("Stage '%s' uses default nutrient multiplier 1.0 (no change to base targets)", stage_key)
    # Apply stage multiplier to base targets
    adjusted_targets = {}
    for nutrient, base_value in base_targets.items():
        try:
            base_val = float(base_value)
        except (ValueError, TypeError):
            _LOGGER.warning("Non-numeric base nutrient target for %s: %s; skipping this nutrient.", nutrient, base_value)
            continue
        adjusted_value = base_val * stage_multiplier
        adjusted_targets[nutrient] = round(adjusted_value, 2)
    # Apply tag-specific nutrient modifiers
    tags = profile.get("general", {}).get("tags") or profile.get("tags") or []
    if tags is None:
        tags = []
    tags_lower = [str(t).lower() for t in tags]
    if tags_lower:
        for tag in tags_lower:
            if tag in TAG_NUTRIENT_MODIFIERS:
                modifiers = TAG_NUTRIENT_MODIFIERS[tag]
                for nut, factor in modifiers.items():
                    if nut in adjusted_targets:
                        old_val = adjusted_targets[nut]
                        new_val = round(old_val * factor, 2)
                        adjusted_targets[nut] = new_val
                        _LOGGER.info("Applying tag modifier '%s': %s target %sx (%.2f -> %.2f)",
                                     tag, nut, factor, old_val, new_val)
                    else:
                        _LOGGER.warning("Tag '%s' indicates adjusting %s, but no base target for %s", tag, nut, nut)
            else:
                _LOGGER.debug("No nutrient adjustment defined for tag '%s'; skipping", tag)
    else:
        _LOGGER.debug("No tags specified for plant '%s'; no tag-based adjustments", plant_id)
    # Save adjusted targets to data/nutrient_targets.json
    data_dir = hass.config.path("data") if hass else os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    targets_path = os.path.join(data_dir, "nutrient_targets.json")
    nutrient_targets_data = {}
    try:
        if os.path.exists(targets_path):
            with open(targets_path, "r", encoding="utf-8") as f:
                nutrient_targets_data = json.load(f)
                if not isinstance(nutrient_targets_data, dict):
                    _LOGGER.warning("nutrient_targets.json content was not a dict; resetting file.")
                    nutrient_targets_data = {}
    except json.JSONDecodeError:
        _LOGGER.warning("nutrient_targets.json found but invalid JSON; resetting file.")
        nutrient_targets_data = {}
    except Exception as e:
        _LOGGER.error("Failed to read nutrient targets file: %s", e)
        nutrient_targets_data = {}
    # Update this plant's entry
    nutrient_targets_data[plant_id] = adjusted_targets
    # Write back to JSON file
    try:
        with open(targets_path, "w", encoding="utf-8") as f:
            json.dump(nutrient_targets_data, f, indent=2)
        _LOGGER.info("Adjusted nutrient targets for plant '%s' saved to %s", plant_id, targets_path)
    except Exception as e:
        _LOGGER.error("Failed to write nutrient targets for plant '%s': %s", plant_id, e)
    return adjusted_targets


__all__ = ["schedule_nutrients"]
