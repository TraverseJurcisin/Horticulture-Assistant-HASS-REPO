"""Helper for loading multi-file plant profiles from disk.

Each plant has its own directory under ``plants/`` containing JSON fragments
describing the profile. This module aggregates those fragments into a single
dictionary which other modules can consume. Validation-only files are skipped by
default to speed up loading in production.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class PlantProfile:
    """Loaded plant profile data."""

    plant_id: str
    profile_data: Dict[str, Dict[str, Any]]

    def as_dict(self) -> Dict[str, Any]:
        """Return profile data as a plain dictionary."""
        return {"plant_id": self.plant_id, "profile_data": self.profile_data}

    # Provide basic mapping-style access for backward compatibility
    def __getitem__(self, item: str) -> Any:
        return self.as_dict()[item]


def load_plant_profile(
    plant_id: str,
    base_path: str | None = None,
    *,
    include_validation_files: bool = False,
) -> dict:
    """
    Load a plant's profile by reading all JSON files in the plant's directory.

    Scans the directory `plants/<plant_id>/` (or under the given base_path) for JSON files,
    except for ``profile_index.json`` and, by default, any files intended for
    validation only.
    Parses each JSON file into a dictionary and aggregates them into a single profile structure.

    Returns a dictionary with the structure:
    {
        'plant_id': <plant_id>,
        'profile_data': {
            <filename_base>: <parsed JSON content as dict>,
            ...
        }
    }

    Any JSON files that fail to parse are skipped with an error logged, while loading of other files continues.
    Logs an info-level summary with the total number of profile modules successfully loaded.

    :param plant_id: Identifier for the plant (also the directory name under the base path).
    :param base_path: Optional base directory for plant profiles (defaults to
        ``plants/`` in the current working directory).
    :param include_validation_files: If ``True``, also load files whose name
        contains ``validate`` or ``validation``.
    :return: A dictionary containing the plant_id and loaded profile_data sections, or an empty dict on error.
    """
    # Determine the base directory and plant profile directory
    base_dir = Path(base_path) if base_path else Path("plants")
    plant_dir = base_dir / str(plant_id)

    # Ensure the plant directory exists
    if not plant_dir.is_dir():
        _LOGGER.error("Plant directory not found: %s", plant_dir)
        return {}

    profile_data = {}
    count_loaded = 0

    # Iterate over all JSON files in the plant directory (sorted for consistency)
    try:
        for file_path in sorted(plant_dir.iterdir(), key=lambda p: p.name):
            if not file_path.is_file() or file_path.suffix.lower() != ".json":
                continue
            filename = file_path.name
            # Skip the profile index file and any validation-only JSON files
            if filename == "profile_index.json":
                continue
            if not include_validation_files and (
                "validation" in filename.lower() or "validate" in filename.lower()
            ):
                _LOGGER.debug("Skipping validation-only file: %s", file_path)
                continue
            # Attempt to load and parse the JSON file
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                _LOGGER.error("Failed to parse JSON file %s: %s", file_path, e)
                continue
            # Ensure the parsed data is a dictionary (profile sections should be dicts)
            if not isinstance(data, dict):
                _LOGGER.warning(
                    "Profile file %s did not contain a JSON object; skipping.",
                    file_path,
                )
                continue
            # Use the filename (without .json extension) as the key in profile_data
            key = file_path.stem
            profile_data[key] = data
            count_loaded += 1
    except Exception as e:
        _LOGGER.error("Error loading profile for plant '%s': %s", plant_id, e)
        return {}

    # If no profile sections were loaded, log an error and return empty
    if count_loaded == 0:
        _LOGGER.error(
            "No profile data loaded for plant '%s' (no valid profile files found).",
            plant_id,
        )
        return {}

    # Log summary of modules loaded
    _LOGGER.info("Loaded %d profile modules for plant '%s'.", count_loaded, plant_id)

    return PlantProfile(plant_id=str(plant_id), profile_data=profile_data)
