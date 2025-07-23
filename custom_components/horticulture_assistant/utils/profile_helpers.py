import os
import logging
from pathlib import Path
from typing import Mapping, Any

from .json_io import save_json

_LOGGER = logging.getLogger(__name__)


def write_profile_sections(
    plant_id: str,
    sections: Mapping[str, Any],
    base_path: str | Path | None = None,
    overwrite: bool = False,
) -> str:
    """Write profile JSON ``sections`` for ``plant_id`` under ``base_path``.

    Returns the ``plant_id`` on success or an empty string on error.
    """
    base_dir = Path(base_path) if base_path else Path("plants")
    plant_dir = base_dir / plant_id
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as err:  # pragma: no cover - unexpected errors
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, err)
        return ""

    for filename, data in sections.items():
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            _LOGGER.info("File %s already exists. Skipping write.", file_path)
            continue
        try:
            save_json(file_path, data)
            if overwrite and file_path.exists():
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as err:  # pragma: no cover - unexpected errors
            _LOGGER.error("Failed to write %s: %s", file_path, err)

    _LOGGER.info("Profile files prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id
