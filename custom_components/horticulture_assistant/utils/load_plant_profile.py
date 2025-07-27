"""Helper for loading multi-file plant profiles from disk.

Each plant has its own directory under ``plants/`` containing JSON fragments
describing the profile. This module aggregates those fragments into a single
dictionary which other modules can consume. Validation-only files are skipped by
default to speed up loading in production.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

_LOGGER = logging.getLogger(__name__)

__all__ = ["PlantProfile", "load_plant_profile", "clear_profile_cache"]


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


@lru_cache(maxsize=None)
def load_plant_profile(
    plant_id: str,
    base_path: str | None = None,
    *,
    include_validation_files: bool = False,
) -> PlantProfile | dict:
    """Return a :class:`PlantProfile` for ``plant_id``.

    All ``*.json`` files found under ``plants/<plant_id>/`` are parsed and
    merged into one profile. ``profile_index.json`` and, by default,
    any files intended solely for validation are skipped. Invalid JSON files are
    logged and ignored so that loading continues for the rest of the profile.

    If no valid profile data is found an empty dict is returned instead of a
    dataclass instance.

    Parameters
    ----------
    plant_id: str
        Identifier for the plant (the profile directory name).
    base_path: str | None, optional
        Base directory of plant profiles, default ``plants/`` in the current
        working directory.
    include_validation_files: bool, optional
        When ``True`` files containing ``validate`` or ``validation`` in the
        name are also loaded.

    Returns
    -------
    PlantProfile | dict
        The aggregated profile information, or ``{}`` if nothing was loaded.
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


def clear_profile_cache() -> None:
    """Clear cached profile results from :func:`load_plant_profile`."""

    load_plant_profile.cache_clear()
