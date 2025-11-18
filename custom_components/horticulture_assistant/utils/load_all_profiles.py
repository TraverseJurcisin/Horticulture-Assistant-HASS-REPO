"""Utilities for loading and validating multiple plant profiles."""

import logging
import os
from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path

from custom_components.horticulture_assistant.utils.load_bio_profile import load_bio_profile
from custom_components.horticulture_assistant.utils.validate_profile_structure import validate_profile_structure

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ProfileLoadResult:
    """Result container for :func:`load_all_profiles`."""

    plant_id: str
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
    base_dir = Path(base_path) if base_path else Path(os.getcwd()) / "plants"
    profiles: dict[str, ProfileLoadResult] = {}
    if not base_dir.is_dir():
        _LOGGER.error("Base directory for plant profiles not found: %s", base_dir)
        return {}
    # Iterate over each subdirectory in the base directory
    for plant_dir in base_dir.iterdir():
        if not plant_dir.is_dir():
            continue  # skip any files in the base directory
        plant_id = plant_dir.name

        profile_obj = load_bio_profile(plant_id, base_path=base_dir)
        if not profile_obj:
            continue

        # Filter loaded sections based on the pattern
        profile_data = {
            name: data for name, data in profile_obj.profile_data.items() if fnmatch(f"{name}.json", pattern)
        }
        if not profile_data:
            # skip this directory if no files match the pattern
            continue

        issues: dict[str, object] = {}
        if validate:
            validation_issues = validate_profile_structure(plant_id, base_path=base_path, verbose=verbose)
            if validation_issues:
                issues = validation_issues

        profiles[plant_id] = ProfileLoadResult(
            plant_id=plant_id,
            loaded=True,
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
