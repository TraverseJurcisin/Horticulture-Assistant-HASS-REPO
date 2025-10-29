"""Helper utilities for writing plant profile sections to disk."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any

from .json_io import save_json

_LOGGER = logging.getLogger(__name__)


def _safe_component(value: str) -> str:
    """Return a filesystem-safe directory name for ``value``."""

    text = (value or "").strip()
    if not text:
        return "plant"

    text = text.replace("\\", "/")
    pure = PurePath(text)
    if pure.parts:
        candidate = pure.name if len(pure.parts) != 1 else pure.parts[0]
    else:
        candidate = text

    candidate = candidate.strip().strip(".")
    if not candidate or candidate in {".", ".."}:
        return "plant"

    safe = candidate.replace("/", "_").replace("\\", "_")
    safe = safe.strip()
    return safe or "plant"


def write_profile_sections(
    plant_id: str,
    sections: Mapping[str, Any],
    base_path: str | Path | None = None,
    overwrite: bool = False,
) -> str:
    """Write profile JSON ``sections`` for ``plant_id`` under ``base_path``.

    Parameters
    ----------
    plant_id:
        Directory name for the plant within ``base_path``.
    sections:
        Mapping of file names to JSON serializable data.
    base_path:
        Optional root directory to create the profile under. Defaults to
        ``./plants``.
    overwrite:
        If ``True`` existing files are replaced. Otherwise they are left
        untouched and logged.

    Returns
    -------
    str
        The ``plant_id`` on success or an empty string if a failure
        prevented writing any files.
    """
    base_dir = Path(base_path) if base_path else Path("plants")
    safe_id = _safe_component(plant_id)
    plant_dir = base_dir / safe_id
    try:
        plant_dir.mkdir(parents=True, exist_ok=True)
    except Exception as err:  # pragma: no cover - unexpected errors
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, err)
        return ""

    had_success = False

    for filename, data in sections.items():
        file_path = plant_dir / filename
        existed = file_path.exists()
        if existed and not overwrite:
            _LOGGER.info("File %s already exists. Skipping write.", file_path)
            had_success = True
            continue
        try:
            save_json(file_path, data)
            if overwrite and existed:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
            had_success = True
        except Exception as err:  # pragma: no cover - unexpected errors
            _LOGGER.error("Failed to write %s: %s", file_path, err)

    if not had_success:
        _LOGGER.error("Unable to create any profile files for '%s'", plant_id)
        return ""

    _LOGGER.info("Profile files prepared for '%s' at %s", plant_id, plant_dir)
    return plant_id
