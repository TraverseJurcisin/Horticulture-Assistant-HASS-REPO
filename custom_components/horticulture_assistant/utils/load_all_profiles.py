"""Utilities for loading and validating multiple plant profiles."""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from plant_engine.utils import get_plants_dir

from custom_components.horticulture_assistant.utils.validate_profile_structure import (
    validate_profile_structure,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ProfileLoadResult:
    """Result container for :func:`load_all_profiles`."""

    loaded: bool
    profile_data: dict
    issues: dict

    def as_dict(self) -> dict:
        """Return result as a plain dictionary."""
        return asdict(self)

def load_all_profiles(
    base_path: str | None = None,
    validate: bool = False,
    verbose: bool = False,
    *,
    pattern: str = "*.json",
) -> dict[str, ProfileLoadResult]:
    """
    Load plant profiles from JSON files under ``base_path``.

    Each plant should have its own folder under ``base_path`` containing one or
    more JSON files. All matching files are loaded and merged into a single
    profile structure. If ``validate`` is ``True`` the profile is checked using
    :func:`validate_profile_structure` and any issues are collected.
    
    :param base_path: Base directory containing plant profile folders (defaults to "./plants").
    :param validate: Whether to perform structural validation on each profile using validate_profile_structure.
    :param verbose: If True, pass verbose=True to the validation for detailed logging of issues.
    :param pattern: Glob pattern of files to load from each plant directory.
    :return: Mapping of plant_id to :class:`ProfileLoadResult` objects.
    """
    base_dir = Path(base_path) if base_path else get_plants_dir()
    profiles: dict[str, ProfileLoadResult] = {}
    if not base_dir.is_dir():
        _LOGGER.error("Base directory for plant profiles not found: %s", base_dir)
        return {}
    # Iterate over each subdirectory in the base directory
    for plant_dir in base_dir.iterdir():
        if not plant_dir.is_dir():
            continue  # skip any files in the base directory
        plant_id = plant_dir.name
        json_files = list(plant_dir.glob(pattern))
        if not json_files:
            # skip this directory if it contains no JSON files
            continue
        profile_data: dict[str, dict] = {}
        issues: dict[str, object] = {}
        loaded_flag = False
        # Load each JSON file in the plant directory
        for file_path in json_files:
            file_name = file_path.name
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = json.load(f)
                if not isinstance(content, dict):
                    raise ValueError("Content is not a dict")
            except Exception as exc:
                if not validate:
                    _LOGGER.error("Failed to load %s: %s", file_path, exc)
                issues[file_name] = {"error": str(exc)}
                continue

            loaded_flag = True
            profile_data[file_path.stem] = content
        # If requested, validate the profile structure and use the results
        if validate:
            validation_issues = validate_profile_structure(plant_id, base_path=base_path, verbose=verbose)
            # Use validation issues if any found (this covers parse errors and structural issues)
            if validation_issues:
                issues = validation_issues
        # Store the results for this plant
        profiles[plant_id] = ProfileLoadResult(
            loaded=loaded_flag,
            profile_data=profile_data,
            issues=issues,
        )
    # Summary logging
    total_profiles = len(profiles)
    profiles_with_issues = sum(1 for data in profiles.values() if data.issues)
    if validate:
        _LOGGER.info("Loaded %d profiles, %d with validation issues.", total_profiles, profiles_with_issues)
    else:
        if profiles_with_issues:
            _LOGGER.info("Loaded %d profiles, %d with issues.", total_profiles, profiles_with_issues)
        else:
            _LOGGER.info("Loaded %d profiles with no issues.", total_profiles)
    return profiles
