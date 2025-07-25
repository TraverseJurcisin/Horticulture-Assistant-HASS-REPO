import os
import json
import logging
from pathlib import Path
from plant_engine.utils import get_plants_dir

_LOGGER = logging.getLogger(__name__)

def generate_profile_index(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """
    Generate or update a profile index file for a given plant.

    This function creates/updates `plants/<plant_id>/profile_index.json`, which contains an index of all JSON
    profile files in the plant's directory. Each entry in the index is a dictionary of metadata (with keys 
    "exists", "last_updated", and "size") for a profile file (e.g., "nutrition.json") present in the directory.
    The output index dictionary is sorted by file name alphabetically.

    If `profile_index.json` already exists and `overwrite` is False, the index generation is skipped.
    If `overwrite` is True or the index file is missing, a new index file is written (or an existing one 
    overwritten) with the collected metadata.

    All actions (skipping, file creation, overwriting) are logged, including an entry for each profile file indexed
    and a summary log with the total count and timestamp.

    :param plant_id: Identifier for the plant (used as directory name under the base path).
    :param base_path: Optional base directory path for plant profiles (defaults to "plants/" in the current working directory).
    :param overwrite: If True, overwrite the existing index file; if False, do not write if an index file already exists.
    :return: The plant_id if the index was successfully generated (or skipped due to existing file), or an empty string on error.
    """
    # Determine base directory for plant profiles
    if base_path:
        base_dir = Path(base_path)
    else:
        base_dir = get_plants_dir()
    plant_dir = base_dir / str(plant_id)

    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return ""

    index_path = plant_dir / "profile_index.json"
    # Skip generation if index file exists and not overwriting
    if index_path.exists() and not overwrite:
        _LOGGER.info("Profile index file already exists: %s. Skipping generation.", index_path)
        return plant_id

    profiles_index = {}
    # Scan for all JSON profile files in the plant directory
    try:
        for file_path in sorted([p for p in plant_dir.iterdir() if p.is_file() and p.suffix.lower() == ".json"], key=lambda x: x.name):
            if file_path.name == "profile_index.json":
                continue  # skip the index file itself
            stat_info = file_path.stat()
            profiles_index[file_path.name] = {
                "exists": True,
                "last_updated": int(stat_info.st_mtime),
                "size": stat_info.st_size
            }
            # Log each profile indexed with metadata
            from datetime import datetime
            ts_str = datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            _LOGGER.info("Indexed profile file: %s (last_updated: %s, size: %d bytes)", file_path, ts_str, stat_info.st_size)
    except Exception as e:
        _LOGGER.error("Failed to scan profiles for plant '%s': %s", plant_id, e)
        return ""

    # Write the profile index JSON file
    try:
        with open(index_path, "w", encoding="utf-8") as idx_file:
            json.dump(profiles_index, idx_file, indent=2)
        if index_path.exists() and overwrite:
            _LOGGER.info("Overwrote existing file: %s", index_path)
        else:
            _LOGGER.info("Created file: %s", index_path)
    except Exception as e:
        _LOGGER.error("Failed to write profile index for '%s': %s", plant_id, e)
        return ""

    # Log summary of indexing
    total_profiles = len(profiles_index)
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _LOGGER.info("Profile index generated for '%s' with %d profiles at %s", plant_id, total_profiles, now_str)

    return plant_id