"""Generate per-plant nutrient targets based on stage and tags."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Mapping, Iterable

try:
    # If running within Home Assistant, this will be available
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None

from custom_components.horticulture_assistant.utils.plant_profile_loader import load_profile
from plant_engine.nutrient_manager import (
    get_recommended_levels,
    get_all_recommended_levels,
    calculate_nutrient_adjustments,
)
from plant_engine.utils import load_json, save_json, load_dataset, normalize_key
from custom_components.horticulture_assistant.utils.path_utils import (
    config_path,
    plants_path,
    data_path,
    ensure_data_dir,
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
def normalize_tag(tag: str) -> str:
    """Return normalized tag string for dataset lookups."""
    return normalize_key(str(tag)).replace("-", "_")


# Tag-specific nutrient modifiers loaded from a dataset.  Users can extend
# or override this mapping by providing ``nutrient_tag_modifiers.json`` in
# the dataset overlay directory.
TAG_MODIFIER_FILE = "nutrients/nutrient_tag_modifiers.json"

from plant_engine.nutrient_absorption import apply_absorption_rates

@lru_cache(maxsize=1)
def _tag_modifiers() -> dict[str, dict[str, float]]:
    """Return normalized tag modifier mapping from the dataset."""
    raw = load_dataset(TAG_MODIFIER_FILE)
    modifiers: dict[str, dict[str, float]] = {}
    for tag, data in raw.items():
        norm_tag = normalize_tag(tag)
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

    reg_path = config_path(hass, PLANT_REGISTRY_FILE)
    try:
        data = load_json(reg_path)
        plant_type = data.get(plant_id, {}).get("plant_type")
        if plant_type:
            return str(plant_type).lower()
    except Exception:
        pass
    return None


@lru_cache(maxsize=None)
def _cached_load_profile(plant_id: str, base_dir: str | None) -> dict:
    """Return loaded plant profile from ``base_dir`` (cached)."""

    return load_profile(plant_id=plant_id, base_dir=base_dir)


def _load_profile(plant_id: str, hass: HomeAssistant | None) -> dict:
    """Return loaded profile for ``plant_id`` using Home Assistant if provided."""

    if hass is not None:
        try:
            base_dir = plants_path(hass)
        except Exception as exc:  # pragma: no cover - HA may not provide path
            _LOGGER.warning("Could not determine plants directory: %s", exc)
            base_dir = plants_path(None)
    else:
        base_dir = plants_path(None)
    return _cached_load_profile(plant_id, base_dir)


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
        mods = modifiers.get(normalize_tag(tag))
        if not mods:
            continue
        for nut, factor in mods.items():
            if nut not in targets:
                continue
            targets[nut] = round(targets[nut] * factor, 2)


def _apply_absorption_rates(targets: dict[str, float], stage_key: str) -> None:
    """Adjust ``targets`` accounting for stage-specific absorption efficiency."""

    adjusted = apply_absorption_rates(targets, stage_key)
    targets.clear()
    targets.update(adjusted)

def _compute_nutrient_targets(
    plant_id: str, hass: HomeAssistant | None, include_micro: bool
) -> dict[str, float]:
    """Return nutrient targets for ``plant_id`` without persisting them.

    This helper consolidates profile data and guideline defaults to produce
    stage-adjusted nutrient targets. Tag modifiers and absorption rates from
    datasets are applied automatically. When ``include_micro`` is ``True``
    micronutrient guidelines are also merged into the result.
    """

    profile = _load_profile(plant_id, hass)
    if not profile:
        _LOGGER.error("Plant profile for '%s' not found or empty", plant_id)
        return {}

    base_targets = profile.get("nutrients") or {}
    stage = (
        profile.get("general", {}).get("lifecycle_stage")
        or profile.get("general", {}).get("stage")
        or profile.get("stage")
        or "unknown"
    )
    stage_key = STAGE_SYNONYMS.get(str(stage).lower(), str(stage).lower())

    plant_type = _get_plant_type(plant_id, profile, hass)
    if plant_type and (include_micro or not base_targets):
        guideline_func = (
            get_all_recommended_levels if include_micro else get_recommended_levels
        )
        guidelines = guideline_func(plant_type, stage_key)
        if guidelines:
            if not base_targets:
                _LOGGER.info(
                    "Using nutrient guidelines for %s (%s stage)",
                    plant_type,
                    stage_key,
                )
            for nut, val in guidelines.items():
                base_targets.setdefault(nut, val)
        elif not base_targets:
            _LOGGER.warning(
                "No nutrient targets for '%s' and no guidelines found",
                plant_id,
            )
            return {}
    elif not base_targets:
        _LOGGER.warning("No nutrient targets for '%s' and no guidelines found", plant_id)
        return {}

    mult = _stage_multiplier(profile, stage_key)
    adjusted: dict[str, float] = {}
    for nut, val in base_targets.items():
        try:
            adjusted[nut] = round(float(val) * mult, 2)
        except (ValueError, TypeError):
            _LOGGER.warning("Invalid base nutrient value for %s: %s", nut, val)

    tags = [str(t).lower() for t in (profile.get("general", {}).get("tags") or profile.get("tags") or [])]
    _apply_tag_modifiers(adjusted, tags)
    _apply_absorption_rates(adjusted, stage_key)

    return adjusted


def schedule_nutrients(
    plant_id: str,
    hass: HomeAssistant = None,
    *,
    include_micro: bool = False,
) -> NutrientTargets:
    """Return adjusted nutrient targets for ``plant_id`` and persist them."""

    adjusted = _compute_nutrient_targets(plant_id, hass, include_micro)
    data_dir = ensure_data_dir(hass)
    path = os.path.join(data_dir, "nutrient_targets.json")
    existing = {}
    if os.path.exists(path):
        try:
            existing = load_json(path)
        except Exception:
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    if adjusted:
        existing[plant_id] = adjusted
    try:
        save_json(path, existing)
    except Exception as exc:  # pragma: no cover - write errors are unlikely
        _LOGGER.error("Failed to write nutrient targets: %s", exc)

    return NutrientTargets(adjusted)


@dataclass
class NutrientAdjustments:
    """PPM adjustments needed to reach guideline targets."""

    values: dict[str, float]

    def as_dict(self) -> dict[str, float]:
        return asdict(self)["values"]


def schedule_nutrient_corrections(
    plant_id: str,
    current_levels: Mapping[str, float],
    hass: HomeAssistant = None,
    *,
    use_synergy: bool = False,
) -> NutrientAdjustments:
    """Return ppm corrections required for ``plant_id`` based on readings.

    Parameters
    ----------
    plant_id:
        Identifier for the plant profile to evaluate.
    current_levels:
        Mapping of current nutrient levels in ppm.
    hass:
        Optional Home Assistant instance for path resolution.
    use_synergy:
        When ``True`` guidelines adjusted by nutrient synergy factors are used.
    """

    profile = _load_profile(plant_id, hass)
    if not profile:
        _LOGGER.error("Plant profile for '%s' not found or empty", plant_id)
        return NutrientAdjustments({})

    stage = (
        profile.get("general", {}).get("lifecycle_stage")
        or profile.get("general", {}).get("stage")
        or profile.get("stage")
        or "unknown"
    )
    stage_key = STAGE_SYNONYMS.get(str(stage).lower(), str(stage).lower())
    plant_type = _get_plant_type(plant_id, profile, hass)
    if not plant_type:
        _LOGGER.warning("Unable to determine plant type for '%s'", plant_id)
        return NutrientAdjustments({})

    if use_synergy:
        from plant_engine.nutrient_manager import (
            calculate_all_deficiencies_with_synergy as _calc,
        )
    else:
        from plant_engine.nutrient_manager import calculate_nutrient_adjustments as _calc

    adjustments = _calc(current_levels, plant_type, stage_key)
    return NutrientAdjustments(adjustments)


def schedule_nutrients_bulk(
    plant_ids: Iterable[str],
    hass: HomeAssistant = None,
    *,
    include_micro: bool = False,
) -> dict[str, dict[str, float]]:
    """Return nutrient targets for multiple plants and store them once."""

    results: dict[str, dict[str, float]] = {}
    for pid in plant_ids:
        targets = _compute_nutrient_targets(pid, hass, include_micro)
        if targets:
            results[pid] = targets

    if results:
        data_dir = ensure_data_dir(hass)
        path = os.path.join(data_dir, "nutrient_targets.json")
        existing = {}
        if os.path.exists(path):
            try:
                existing = load_json(path)
            except Exception:
                existing = {}
        if not isinstance(existing, dict):
            existing = {}
        existing.update(results)
        try:
            save_json(path, existing)
        except Exception as exc:  # pragma: no cover - write errors are unlikely
            _LOGGER.error("Failed to write nutrient targets: %s", exc)

    return results


__all__ = [
    "schedule_nutrients",
    "schedule_nutrient_corrections",
    "schedule_nutrients_bulk",
    "normalize_tag",
]
