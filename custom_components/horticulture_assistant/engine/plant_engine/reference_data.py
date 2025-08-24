"""Convenient access to common horticultural reference datasets."""

from __future__ import annotations

from functools import cache
from typing import Any

from .utils import clear_dataset_cache, load_dataset, normalize_key

# Mapping of logical keys to dataset file names used across the project.
# Additional datasets can be appended here without altering code that
# consumes :func:`load_reference_data` or :func:`get_reference_dataset`.
REFERENCE_FILES: dict[str, str] = {
    "nutrient_guidelines": "nutrients/nutrient_guidelines.json",
    "micronutrient_guidelines": "nutrients/micronutrient_guidelines.json",
    "nutrient_ratio_guidelines": "nutrients/nutrient_ratio_guidelines.json",
    "environment_guidelines": "environment/environment_guidelines.json",
    "pest_guidelines": "pests/pest_guidelines.json",
    "pest_monitoring_intervals": "pests/pest_monitoring_intervals.json",
    "ipm_guidelines": "pests/ipm_guidelines.json",
    "pest_management_guidelines": "pests/pest_management_guidelines.json",
    "growth_stages": "stages/growth_stages.json",
    "stage_tasks": "stages/stage_tasks.json",
    "total_nutrient_requirements": "nutrients/total_nutrient_requirements.json",
    "stage_nutrient_requirements": "nutrients/stage_nutrient_requirements.json",
    # newly exposed reference datasets
    "nutrient_synergies": "nutrients/nutrient_synergies.json",
    "disease_guidelines": "diseases/disease_guidelines.json",
    # daily water usage requirements per growth stage
    "water_usage_guidelines": "water/water_usage_guidelines.json",
}

__all__ = [
    "load_reference_data",
    "get_reference_dataset",
    "get_plant_overview",
    "refresh_reference_data",
    "REFERENCE_FILES",
]


@cache
def load_reference_data() -> dict[str, dict[str, Any]]:
    """Return consolidated horticultural reference datasets.

    Results are cached so repeated lookups do not trigger additional disk
    reads. The return value maps each key in :data:`REFERENCE_FILES` to the
    parsed dataset contents (or an empty ``dict`` if the file is missing or
    invalid).
    """

    data: dict[str, dict[str, Any]] = {}
    for key, filename in REFERENCE_FILES.items():
        content = load_dataset(filename)
        data[key] = content if isinstance(content, dict) else {}
    return data


def get_reference_dataset(name: str) -> dict[str, Any]:
    """Return a specific reference dataset by ``name``."""

    return load_reference_data().get(name, {})


def get_plant_overview(plant_type: str) -> dict[str, Any]:
    """Return consolidated reference info for ``plant_type``.

    The overview includes nutrient, environment and pest guidelines along with
    growth stage details and common tasks. Missing datasets return empty
    mappings so callers don't need to handle ``KeyError``.
    """

    key = normalize_key(plant_type)
    data = load_reference_data()

    def entry(name: str) -> dict[str, Any]:
        dataset = data.get(name, {})
        if isinstance(dataset, dict):
            return dataset.get(key, {}) if dataset else {}
        return {}

    return {
        "nutrients": entry("nutrient_guidelines"),
        "micronutrients": entry("micronutrient_guidelines"),
        "ratios": entry("nutrient_ratio_guidelines"),
        "environment": entry("environment_guidelines"),
        "pests": entry("pest_guidelines"),
        "ipm": entry("ipm_guidelines"),
        "pest_management": entry("pest_management_guidelines"),
        "monitoring_intervals": entry("pest_monitoring_intervals"),
        "stages": entry("growth_stages"),
        "tasks": entry("stage_tasks"),
        "total_requirements": entry("total_nutrient_requirements"),
        "stage_requirements": entry("stage_nutrient_requirements"),
        "water_usage": entry("water_usage_guidelines"),
    }


def refresh_reference_data() -> None:
    """Clear cached datasets so they are reloaded on next access."""

    load_reference_data.cache_clear()
    clear_dataset_cache()
