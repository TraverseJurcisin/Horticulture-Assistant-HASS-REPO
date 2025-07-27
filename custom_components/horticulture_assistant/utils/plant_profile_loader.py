"""Helpers for loading structured plant profile data."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from functools import lru_cache
from typing import Any, Mapping

from .json_io import load_json, save_json

# Attempt to import PyYAML for optional YAML support. Tests fall back to a very
# small parser that understands the limited subset of YAML used in fixtures.
try:
    import yaml
except ImportError:
    yaml = None

_LOGGER = logging.getLogger(__name__)

# Environment variable name for overriding the default profile directory
_ENV_PLANT_DIR = "HORTICULTURE_PLANT_DIR"


def get_default_base_dir() -> Path:
    """Return the base directory used for plant profiles."""

    return Path(os.getenv(_ENV_PLANT_DIR, "plants"))


DEFAULT_BASE_DIR = get_default_base_dir()

REQUIRED_THRESHOLD_KEYS = {"light", "temperature", "EC"}
REQUIRED_STAGE_KEY = "stage_duration"


def parse_basic_yaml(content: str) -> dict:
    """Return a naive YAML parser used when PyYAML is unavailable.

    The implementation supports the extremely small subset of YAML used in
    unit tests: nested dictionaries through indentation and single line lists.
    Values that look numeric are converted to ``int`` or ``float``.
    """

    parsed: dict[str, object] = {}
    stack = [parsed]
    indents = [0]
    for line in content.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(":")
        while indent <= indents[-1] and len(stack) > 1:
            stack.pop()
            indents.pop()
        if value.strip() == "":
            obj = {}
            stack[-1][key] = obj
            stack.append(obj)
            indents.append(indent)
            continue
        val = value.strip()
        if val.startswith("[") and val.endswith("]"):
            items = [i.strip() for i in val[1:-1].split(",") if i.strip()]
            val = [float(i) if i.replace(".", "", 1).isdigit() else i for i in items]
        else:
            if val.replace(".", "", 1).isdigit():
                val = float(val) if "." in val else int(val)
        stack[-1][key] = val
    return parsed

@lru_cache(maxsize=None)
def load_profile_from_path(path: str | Path) -> dict:
    """
    Load a plant profile from a file (YAML or JSON) given a filesystem path.
    Returns a structured dict with keys: general, thresholds, stages, nutrients.
    """
    path_obj = Path(path)
    if not path_obj.is_file():
        _LOGGER.error("Profile file not found: %s", path_obj)
        return {}
    ext = path_obj.suffix.lower()

    def _load_yaml(fp: Path) -> dict:
        content = fp.read_text(encoding="utf-8")
        if yaml is not None:
            return yaml.safe_load(content) or {}
        return parse_basic_yaml(content)

    try:
        if ext == ".json":
            data = load_json(str(path_obj))
        elif ext in {".yaml", ".yml"}:
            data = _load_yaml(path_obj)
        else:
            _LOGGER.error("Unsupported profile file extension: %s", ext)
            return {}
    except Exception as exc:
        _LOGGER.error("Failed to parse profile file %s: %s", path_obj, exc)
        return {}

    if not isinstance(data, dict):
        _LOGGER.error("Profile content is not a dictionary: %s", path)
        return {}

    # Initialize structured profile
    profile = {
        "general": {},
        "thresholds": {},
        "stages": {},
        "nutrients": {}
    }
    # Fill sections if present
    general = data.get("general")
    if isinstance(general, dict):
        profile["general"].update(general)
    thresholds = data.get("thresholds")
    if isinstance(thresholds, dict):
        profile["thresholds"].update(thresholds)
    stages = data.get("stages")
    if isinstance(stages, dict):
        profile["stages"] = stages
    nutrients = data.get("nutrients")
    if isinstance(nutrients, dict):
        profile["nutrients"] = nutrients

    # Any other top-level keys go into 'general'
    for key, value in data.items():
        if key not in profile:
            profile["general"][key] = value

    # Validate required keys and log debug messages if missing
    if profile["thresholds"]:
        for key in REQUIRED_THRESHOLD_KEYS:
            if key not in profile["thresholds"]:
                _LOGGER.debug("Profile missing threshold '%s' in file %s", key, path)
    else:
        _LOGGER.debug("No thresholds section defined in profile %s", path)

    if profile["stages"]:
        for stage_name, stage_data in profile["stages"].items():
            if not isinstance(stage_data, dict):
                _LOGGER.debug("Stage '%s' in %s is not a dict", stage_name, path)
                continue
            if REQUIRED_STAGE_KEY not in stage_data:
                _LOGGER.debug("Stage '%s' missing '%s' in profile %s", stage_name, REQUIRED_STAGE_KEY, path)
    else:
        _LOGGER.debug("No stages defined in profile %s", path)

    return profile

@lru_cache(maxsize=None)
def load_profile_by_id(plant_id: str, base_dir: str | Path | None = None) -> dict:
    """
    Load a plant profile by plant_id. Looks for 'plant_id.json' or 'plant_id.yaml' in base_dir or current directory.
    """
    directory = Path(base_dir) if base_dir else get_default_base_dir()
    json_path = directory / f"{plant_id}.json"
    yaml_path = directory / f"{plant_id}.yaml"
    yml_path = directory / f"{plant_id}.yml"

    if json_path.is_file():
        return load_profile_from_path(str(json_path))
    if yaml_path.is_file():
        return load_profile_from_path(str(yaml_path))
    if yml_path.is_file():
        return load_profile_from_path(str(yml_path))

    _LOGGER.error("No plant profile file found for plant_id '%s' in directory %s", plant_id, directory)
    return {}

def load_profile(
    plant_id: str | None = None,
    path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict:
    """
    Load a plant profile given either a plant_id or a filesystem path.
    If 'path' is provided, load from that file directly. Otherwise, use plant_id.
    """
    if path:
        return load_profile_from_path(path)
    if plant_id:
        return load_profile_by_id(plant_id, base_dir)
    _LOGGER.error("No plant_id or path specified for loading profile")
    return {}


def list_available_profiles(base_dir: str | Path | None = None) -> list[str]:
    """Return all plant IDs with a profile file in ``base_dir``.

    The helper scans for ``*.json``, ``*.yaml`` and ``*.yml`` files and
    returns their stem names sorted alphabetically. When the directory does
    not exist an empty list is returned.
    """

    directory = Path(base_dir) if base_dir else get_default_base_dir()
    if not directory.is_dir():
        return []

    plant_ids: set[str] = set()
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() in {".json", ".yaml", ".yml"}:
            plant_ids.add(entry.stem)

    return sorted(plant_ids)


def save_profile_to_path(profile: dict, path: str | Path) -> bool:
    """Write ``profile`` to ``path`` as JSON."""
    try:
        save_json(str(path), profile)
    except Exception as exc:  # pragma: no cover - unexpected file errors
        _LOGGER.error("Failed to write profile %s: %s", path, exc)
        return False
    return True


def save_profile_by_id(
    plant_id: str, profile: dict, base_dir: str | Path | None = None
) -> bool:
    """Write profile for ``plant_id`` under ``base_dir``."""
    directory = Path(base_dir) if base_dir else get_default_base_dir()
    file_path = directory / f"{plant_id}.json"
    return save_profile_to_path(profile, file_path)


def profile_exists(plant_id: str, base_dir: str | Path | None = None) -> bool:
    """Return ``True`` if a profile file exists for ``plant_id``."""

    directory = Path(base_dir) if base_dir else get_default_base_dir()
    for ext in (".json", ".yaml", ".yml"):
        if (directory / f"{plant_id}{ext}").is_file():
            return True
    return False


def delete_profile_by_id(plant_id: str, base_dir: str | Path | None = None) -> bool:
    """Delete the profile file for ``plant_id``."""

    directory = Path(base_dir) if base_dir else get_default_base_dir()
    deleted = False
    for ext in (".json", ".yaml", ".yml"):
        path = directory / f"{plant_id}{ext}"
        if path.is_file():
            try:
                path.unlink()
                deleted = True
            except Exception as exc:  # pragma: no cover - unexpected file errors
                _LOGGER.error("Failed to delete profile %s: %s", path, exc)
    return deleted


def validate_profile(profile: Mapping[str, Any]) -> list[str]:
    """Return a list of missing required keys for ``profile``.

    The function checks for ``plant_id``, ``display_name`` and ``stage`` at the
    top level, along with a ``sensor_entities`` mapping either in the root or
    under ``general``. The returned list is empty when the profile appears
    valid.
    """

    missing: list[str] = []

    for key in ("plant_id", "display_name", "stage"):
        if key not in profile:
            missing.append(key)

    container = profile.get("general", profile)
    if not isinstance(container, Mapping) or "sensor_entities" not in container:
        missing.append("sensor_entities")

    return missing


def update_profile_sensors(
    plant_id: str,
    sensors: dict,
    base_dir: str | Path | None = None,
) -> bool:
    """Update ``sensor_entities`` for ``plant_id`` and save the profile."""
    if not isinstance(sensors, dict):
        return False
    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False

    container = (
        profile.get("general") if isinstance(profile.get("general"), dict) else profile
    )
    for key, val in sensors.items():
        if isinstance(val, str):
            val = [val]
        container.setdefault("sensor_entities", {})[key] = list(val)
    if container is not profile:
        profile["general"] = container

    return save_profile_by_id(plant_id, profile, base_dir)


def attach_profile_sensors(
    plant_id: str,
    sensors: dict,
    base_dir: str | Path | None = None,
) -> bool:
    """Append ``sensors`` entries to the profile without overwriting existing values."""
    if not isinstance(sensors, dict):
        return False

    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False

    container = (
        profile.get("general") if isinstance(profile.get("general"), dict) else profile
    )
    mapping = container.setdefault("sensor_entities", {})
    for key, val in sensors.items():
        if isinstance(val, str):
            val = [val]
        existing = mapping.get(key, [])
        for item in val:
            if item not in existing:
                existing.append(item)
        mapping[key] = existing
    if container is not profile:
        profile["general"] = container

    return save_profile_by_id(plant_id, profile, base_dir)


def detach_profile_sensors(
    plant_id: str,
    sensors: dict,
    base_dir: str | Path | None = None,
) -> bool:
    """Remove sensor mappings from ``plant_id`` and save the profile."""
    if not isinstance(sensors, dict):
        return False

    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False

    container = (
        profile.get("general") if isinstance(profile.get("general"), dict) else profile
    )
    sensor_map = container.get("sensor_entities", {})
    for key, val in sensors.items():
        if key not in sensor_map:
            continue
        if val is None:
            sensor_map.pop(key, None)
            continue
        if isinstance(val, str):
            val = [val]
        sensor_map[key] = [s for s in sensor_map.get(key, []) if s not in val]
        if not sensor_map[key]:
            sensor_map.pop(key, None)

    if sensor_map:
        container["sensor_entities"] = sensor_map
    else:
        container.pop("sensor_entities", None)

    if container is not profile:
        profile["general"] = container

    return save_profile_by_id(plant_id, profile, base_dir)


__all__ = [
    "get_default_base_dir",
    "parse_basic_yaml",
    "load_profile_from_path",
    "load_profile_by_id",
    "load_profile",
    "list_available_profiles",
    "save_profile_to_path",
    "save_profile_by_id",
    "profile_exists",
    "delete_profile_by_id",
    "validate_profile",
    "update_profile_sensors",
    "attach_profile_sensors",
    "detach_profile_sensors",
]
