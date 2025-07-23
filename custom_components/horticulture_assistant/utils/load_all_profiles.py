"""Utilities for loading and validating multiple plant profiles."""

import os
import json
import logging
from pathlib import Path
from custom_components.horticulture_assistant.utils.validate_profile_structure import validate_profile_structure

_LOGGER = logging.getLogger(__name__)

def load_all_profiles(base_path: str = None, validate: bool = False, verbose: bool = False):
    """
    Load all plant profiles from JSON files in each subdirectory of the plants directory.
    Each plant profile is expected to be a folder under the base path (default "./plants").
    For each plant folder, all JSON files are read and combined into a profile data structure.
    Optionally, validate each profile's structure using validate_profile_structure and collect issues.
    
    :param base_path: Base directory containing plant profile folders (defaults to "./plants").
    :param validate: Whether to perform structural validation on each profile using validate_profile_structure.
    :param verbose: If True, pass verbose=True to the validation for detailed logging of issues.
    :return: Dictionary mapping plant_id to a dict with keys:
             "loaded" (bool), "profile_data" (dict), and "issues" (dict of any problems found).
    """
    base_dir = Path(base_path) if base_path else Path(os.getcwd()) / "plants"
    profiles = {}
    if not base_dir.is_dir():
        _LOGGER.error("Base directory for plant profiles not found: %s", base_dir)
        return {}
    # Iterate over each subdirectory in the base directory
    for plant_dir in base_dir.iterdir():
        if not plant_dir.is_dir():
            continue  # skip any files in the base directory
        plant_id = plant_dir.name
        json_files = list(plant_dir.glob("*.json"))
        if not json_files:
            # skip this directory if it contains no JSON files
            continue
        profile_data = {}
        issues = {}
        loaded_flag = False
        # Load each JSON file in the plant directory
        for file_path in json_files:
            file_name = file_path.name
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = json.load(f)
            except Exception as e:
                # Log parse errors unless validation will handle it
                if not validate:
                    _LOGGER.error("Failed to read/parse JSON file %s: %s", file_path, e)
                issues[file_name] = {"error": f"JSON parse error: {e}"}
                continue
            if not isinstance(content, dict):
                if not validate:
                    _LOGGER.warning("Profile file %s is not a JSON object (dict).", file_path)
                issues[file_name] = {"error": "Content is not a dict"}
                continue
            # If loaded successfully, add to profile_data under a key based on the file name (without extension)
            loaded_flag = True
            profile_data[file_path.stem] = content
        # If requested, validate the profile structure and use the results
        if validate:
            validation_issues = validate_profile_structure(plant_id, base_path=base_path, verbose=verbose)
            # Use validation issues if any found (this covers parse errors and structural issues)
            if validation_issues:
                issues = validation_issues
        # Store the results for this plant
        profiles[plant_id] = {
            "loaded": loaded_flag,
            "profile_data": profile_data,
            "issues": issues
        }
    # Summary logging
    total_profiles = len(profiles)
    profiles_with_issues = sum(1 for data in profiles.values() if data["issues"])
    if validate:
        _LOGGER.info("Loaded %d profiles, %d with validation issues.", total_profiles, profiles_with_issues)
    else:
        if profiles_with_issues:
            _LOGGER.info("Loaded %d profiles, %d with issues.", total_profiles, profiles_with_issues)
        else:
            _LOGGER.info("Loaded %d profiles with no issues.", total_profiles)
    return profiles
