"""Helper utilities for writing plant profile sections to disk."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any

from .json_io import save_json

_LOGGER = logging.getLogger(__name__)

_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *{f"com{idx}" for idx in range(1, 10)},
    *{f"lpt{idx}" for idx in range(1, 10)},
}

_WINDOWS_INVALID_CHARS = '<>:"\\|?*'


def _safe_component(value: Any) -> str:
    """Return a filesystem-safe directory name for ``value``."""

    if isinstance(value, str):
        text = value
    elif value is None:
        text = ""
    else:
        text = str(value)
    text = text.strip()
    if not text:
        return "plant"

    text = text.replace("\\", "/")
    pure = PurePath(text)

    segments: list[str] = []
    for segment in pure.parts:
        cleaned = segment.strip()
        if not cleaned or cleaned in {".", ".."}:
            continue
        segments.append(cleaned)

    if not segments:
        candidate = text.strip().strip("./")
        if candidate:
            segments = [candidate]
        else:
            return "plant"

    normalised_parts: list[str] = []
    for segment in segments:
        safe = segment.replace("/", "_").replace("\\", "_")
        for char in _WINDOWS_INVALID_CHARS:
            if char in safe:
                safe = safe.replace(char, "_")
        safe = safe.strip().strip(".")
        if not safe:
            continue

        stem, *suffix = safe.split(".")
        stem_lower = stem.lower()
        if stem_lower in _WINDOWS_RESERVED_NAMES:
            safe_value = f"{stem_lower}_profile"
            if suffix:
                cleaned_suffix = "_".join(part for part in suffix if part)
                cleaned_suffix = cleaned_suffix.replace(".", "_").strip("_")
                if cleaned_suffix:
                    safe_value = f"{safe_value}_{cleaned_suffix}"
        else:
            trailing = "_".join(part for part in suffix if part)
            safe_value = f"{stem}_{trailing}".replace(".", "_") if trailing else stem

        safe_value = safe_value.strip("_")
        if safe_value:
            normalised_parts.append(safe_value)

    if not normalised_parts:
        return "plant"

    return "_".join(normalised_parts)


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
        try:
            relative = PurePath(filename)
        except TypeError:
            _LOGGER.warning("Skipping invalid filename %r for '%s'", filename, plant_id)
            continue

        if relative.is_absolute() or ".." in relative.parts:
            _LOGGER.warning("Skipping unsafe path '%s' for '%s'", relative, plant_id)
            continue

        safe_parts = [part for part in relative.parts if part not in {"", "."}]
        if not safe_parts:
            _LOGGER.warning("Skipping empty path component '%s' for '%s'", relative, plant_id)
            continue

        file_path = plant_dir.joinpath(*safe_parts)
        try:
            file_path.relative_to(plant_dir)
        except ValueError:
            _LOGGER.warning("Skipping unsafe path '%s' for '%s'", relative, plant_id)
            continue

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
