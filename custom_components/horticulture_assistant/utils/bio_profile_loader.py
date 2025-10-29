"""Utilities for loading edge BioProfile documents from disk.

The legacy integration exposed a ``plant_profile_loader`` module that returned
loosely structured dictionaries pieced together from JSON/YAML files.  The
BioProfile v3.3 overhaul requires richer metadata and alignment with the new
hierarchical dataclasses.  This module modernises the helpers while keeping the
familiar entry points used throughout the repository.

Callers can continue to work with plain dictionaries via :func:`load_profile`
and :func:`load_profile_by_id`.  New helpers (:func:`load_bio_profile_by_id`
and :func:`load_bio_profile`) provide :class:`~custom_components.
horticulture_assistant.profile.schema.BioProfile` instances when higher level
behaviour is required.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any

from ..profile.schema import BioProfile
from ..profile.utils import normalise_profile_payload
from .json_io import load_json, save_json

# Attempt to import PyYAML for optional YAML support. Tests fall back to a very
# small parser that understands the limited subset of YAML used in fixtures.
try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

_LOGGER = logging.getLogger(__name__)

# Default directory containing individual profile definitions
DEFAULT_BASE_DIR = Path("plants")
# Environment variable override for the profile directory
PROFILE_DIR_ENV = "HORTICULTURE_PROFILE_DIR"


def profile_base_dir(base_dir: str | Path | None = None) -> Path:
    """Return the directory used for BioProfile fragments."""
    if base_dir is not None:
        return Path(base_dir)
    env = os.getenv(PROFILE_DIR_ENV)
    return Path(env).expanduser() if env else DEFAULT_BASE_DIR


# Supported file extensions for profile files
PROFILE_EXTS: tuple[str, ...] = (".json", ".yaml", ".yml")

REQUIRED_THRESHOLD_KEYS = {"light", "temperature", "EC"}
REQUIRED_STAGE_KEY = "stage_duration"


def parse_basic_yaml(content: str) -> dict:
    """Return a naive YAML parser used when PyYAML is unavailable.

    The parser understands only the limited subset of YAML present in the
    unit test fixtures: nested mappings using indentation and single line
    lists. Numeric values are converted to ``int`` or ``float`` when
    possible.
    """

    parsed: dict[str, object] = {}
    node_stack = [parsed]
    indent_stack = [0]

    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue

        indent = len(raw_line) - len(raw_line.lstrip())
        key, _, value = line.lstrip().partition(":")

        # adjust the stack to the current indentation level
        while indent <= indent_stack[-1] and len(node_stack) > 1:
            node_stack.pop()
            indent_stack.pop()

        if not value:
            obj: dict = {}
            node_stack[-1][key] = obj
            node_stack.append(obj)
            indent_stack.append(indent)
            continue

        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [i.strip() for i in value[1:-1].split(",") if i.strip()]
            parsed_items = []
            for item in items:
                if item.replace(".", "", 1).isdigit():
                    parsed_items.append(float(item) if "." in item else int(item))
                else:
                    parsed_items.append(item)
            parsed_value = parsed_items
        else:
            if value.replace(".", "", 1).isdigit():
                parsed_value = float(value) if "." in value else int(value)
            else:
                parsed_value = value

        node_stack[-1][key] = parsed_value

    return parsed


def get_profile_path(
    plant_id: str, base_dir: str | Path | None = None, *, exts: Iterable[str] = PROFILE_EXTS
) -> Path | None:
    """Return the first existing profile path for ``plant_id``.

    Parameters
    ----------
    plant_id : str
        Profile identifier without extension.
    base_dir : str | Path | None
        Optional directory containing the profile files. Defaults to
        :data:`DEFAULT_BASE_DIR`.
    exts : Iterable[str]
        File extensions to search for in order.

    Returns
    -------
    Path | None
        Path of the profile file if found, otherwise ``None``.
    """

    directory = profile_base_dir(base_dir)
    for ext in exts:
        path = directory / f"{plant_id}{ext}"
        if path.is_file():
            return path
    return None


def _path_cache_key(path: str | Path) -> str:
    """Return a stable cache key for ``path`` regardless of type."""

    return str(Path(path))


@cache
def _load_profile_from_path_cached(path_key: str) -> dict:
    """Return the parsed mapping for ``path_key`` using cached IO."""

    path_obj = Path(path_key)
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
        _LOGGER.error("Profile content is not a dictionary: %s", path_obj)
        return {}

    # Initialize structured profile
    profile = {"general": {}, "thresholds": {}, "stages": {}, "nutrients": {}}
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
                    _LOGGER.debug("Profile missing threshold '%s' in file %s", key, path_obj)
    else:
        _LOGGER.debug("No thresholds section defined in profile %s", path_obj)

    if profile["stages"]:
        for stage_name, stage_data in profile["stages"].items():
            if not isinstance(stage_data, dict):
                _LOGGER.debug("Stage '%s' in %s is not a dict", stage_name, path_obj)
                continue
            if REQUIRED_STAGE_KEY not in stage_data:
                _LOGGER.debug(
                    "Stage '%s' missing '%s' in profile %s", stage_name, REQUIRED_STAGE_KEY, path_obj
                )
    else:
        _LOGGER.debug("No stages defined in profile %s", path_obj)

    return profile


def load_profile_from_path(path: str | Path) -> dict:
    """Return the legacy mapping structure for the file at ``path``.

    The function mirrors the historical behaviour used by several offline
    scripts.  Modern callers that need the BioProfile dataclass should prefer
    :func:`load_bio_profile` or :func:`load_bio_profile_by_id`.
    """

    cached = _load_profile_from_path_cached(_path_cache_key(path))
    return deepcopy(cached)


def _base_dir_cache_key(base_dir: str | Path | None) -> str | None:
    """Return a stable cache key for ``base_dir`` values."""

    if base_dir is None:
        return None
    return str(Path(base_dir))


@cache
def _load_profile_by_id_cached(plant_id: str, base_dir_key: str | None) -> dict:
    """Return structured profile data for ``plant_id`` using cached IO."""

    path = get_profile_path(plant_id, base_dir_key)
    if path:
        return _load_profile_from_path_cached(_path_cache_key(path))

    directory = profile_base_dir(base_dir_key)
    _LOGGER.error(
        "No BioProfile file found for profile '%s' in directory %s",
        plant_id,
        directory,
    )
    return {}


def load_profile_by_id(plant_id: str, base_dir: str | Path | None = None) -> dict:
    """Return structured profile data for ``plant_id``."""

    cached = _load_profile_by_id_cached(plant_id, _base_dir_cache_key(base_dir))
    return deepcopy(cached)


def clear_profile_cache() -> None:
    """Clear cached BioProfile payloads."""

    _load_profile_from_path_cached.cache_clear()
    _load_profile_by_id_cached.cache_clear()


def _normalise_payload(payload: Mapping[str, Any], plant_id: str) -> dict[str, Any]:
    """Return a canonical mapping suitable for :class:`BioProfile`."""

    display_name = payload.get("display_name") or payload.get("name") or plant_id
    normalised = normalise_profile_payload(payload, fallback_id=str(plant_id), display_name=display_name)
    normalised.setdefault("name", normalised.get("display_name"))
    return normalised


def load_bio_profile_by_id(plant_id: str, base_dir: str | Path | None = None) -> BioProfile | None:
    """Return a :class:`BioProfile` for ``plant_id`` if available."""

    payload = load_profile_by_id(plant_id, base_dir)
    if not payload:
        return None
    normalised = _normalise_payload(payload, plant_id)
    return BioProfile.from_json(normalised)


def load_profile(
    plant_id: str | None = None,
    path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> dict:
    """Return the legacy mapping for ``plant_id`` or ``path``."""
    if path:
        return load_profile_from_path(path)
    if plant_id:
        return load_profile_by_id(plant_id, base_dir)
    _LOGGER.error("No plant_id or path specified for loading profile")
    return {}


def load_bio_profile(
    plant_id: str | None = None,
    path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> BioProfile | None:
    """Return a :class:`BioProfile` mirroring :func:`load_profile` semantics."""

    if path:
        raw = load_profile_from_path(path)
        if not raw:
            return None
        normalised = _normalise_payload(raw, Path(path).stem)
        return BioProfile.from_json(normalised)
    if plant_id:
        return load_bio_profile_by_id(plant_id, base_dir)
    _LOGGER.error("No plant_id or path specified for loading profile")
    return None


def list_available_profiles(base_dir: str | Path | None = None) -> list[str]:
    """Return all BioProfile identifiers stored in ``base_dir``."""

    directory = profile_base_dir(base_dir)
    if not directory.is_dir():
        return []

    plant_ids: set[str] = set()
    for ext in PROFILE_EXTS:
        for path in directory.glob(f"*{ext}"):
            if path.is_file():
                plant_ids.add(path.stem)

    return sorted(plant_ids)


def save_profile_to_path(profile: dict, path: str | Path) -> bool:
    """Write ``profile`` to ``path`` as JSON."""
    try:
        save_json(str(path), profile)
    except Exception as exc:  # pragma: no cover - unexpected file errors
        _LOGGER.error("Failed to write profile %s: %s", path, exc)
        return False
    return True


def save_profile_by_id(plant_id: str, profile: dict, base_dir: str | Path | None = None) -> bool:
    """Write profile for ``plant_id`` under ``base_dir``."""
    directory = profile_base_dir(base_dir)
    file_path = directory / f"{plant_id}.json"
    return save_profile_to_path(profile, file_path)


def save_bio_profile(
    profile: BioProfile,
    *,
    base_dir: str | Path | None = None,
    name: str | None = None,
) -> bool:
    """Persist ``profile`` to disk using :func:`save_profile_by_id` semantics."""

    payload = deepcopy(profile.to_json())
    payload.setdefault("display_name", profile.display_name)
    payload.setdefault("name", profile.display_name)
    plant_id = name or profile.profile_id
    return save_profile_by_id(plant_id, payload, base_dir)


def profile_exists(plant_id: str, base_dir: str | Path | None = None) -> bool:
    """Return ``True`` if a profile file exists for ``plant_id``."""
    return get_profile_path(plant_id, base_dir) is not None


def delete_profile_by_id(plant_id: str, base_dir: str | Path | None = None) -> bool:
    """Delete the profile file for ``plant_id``."""
    directory = profile_base_dir(base_dir)
    deleted = False
    for ext in PROFILE_EXTS:
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


def _get_sensor_container(profile: Mapping[str, Any]) -> dict:
    """Return profile section containing ``sensor_entities``."""

    container = profile.get("general")
    return container if isinstance(container, dict) else profile


def _normalize_sensor_values(sensors: Mapping[str, Any]) -> dict[str, list]:
    """Return ``sensors`` with all entries coerced to lists of strings."""

    normalized: dict[str, list[str]] = {}
    for key, val in sensors.items():
        if isinstance(val, str) or not isinstance(val, Iterable):
            values = [val]
        else:
            values = list(val)

        items: list[str] = []
        for item in values:
            try:
                text = str(item)
            except Exception:
                continue
            if text not in items:
                items.append(text)
        normalized[key] = items

    return normalized


def update_profile_sensors(
    plant_id: str,
    sensors: Mapping[str, Any],
    base_dir: str | Path | None = None,
) -> bool:
    """Replace ``sensor_entities`` mapping for ``plant_id``."""

    if not isinstance(sensors, Mapping):
        return False

    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False

    container = _get_sensor_container(profile)
    mapping = _normalize_sensor_values(sensors)
    if mapping:
        container["sensor_entities"] = mapping
    else:
        container.pop("sensor_entities", None)
    if container is not profile:
        profile["general"] = container

    return save_profile_by_id(plant_id, profile, base_dir)


def attach_profile_sensors(
    plant_id: str,
    sensors: Mapping[str, Any],
    base_dir: str | Path | None = None,
) -> bool:
    """Append ``sensors`` entries to the profile without overwriting existing values."""
    if not isinstance(sensors, Mapping):
        return False

    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False

    container = _get_sensor_container(profile)
    mapping = container.setdefault("sensor_entities", {})
    for key, values in _normalize_sensor_values(sensors).items():
        existing = mapping.get(key, [])
        for item in values:
            if item not in existing:
                existing.append(item)
        mapping[key] = existing
    if container is not profile:
        profile["general"] = container

    return save_profile_by_id(plant_id, profile, base_dir)


def detach_profile_sensors(
    plant_id: str,
    sensors: Mapping[str, Any],
    base_dir: str | Path | None = None,
) -> bool:
    """Remove sensor mappings from ``plant_id`` and save the profile."""
    if not isinstance(sensors, Mapping):
        return False

    profile = load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False

    container = _get_sensor_container(profile)
    sensor_map = container.get("sensor_entities", {})
    normalized = _normalize_sensor_values(sensors)
    for key, val in normalized.items():
        if key not in sensor_map:
            continue
        if val is None or len(val) == 0:
            sensor_map.pop(key, None)
            continue
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
    "parse_basic_yaml",
    "profile_base_dir",
    "get_profile_path",
    "load_profile_from_path",
    "load_profile_by_id",
    "load_profile",
    "load_bio_profile",
    "load_bio_profile_by_id",
    "clear_profile_cache",
    "list_available_profiles",
    "save_profile_to_path",
    "save_profile_by_id",
    "save_bio_profile",
    "profile_exists",
    "delete_profile_by_id",
    "validate_profile",
    "update_profile_sensors",
    "attach_profile_sensors",
    "detach_profile_sensors",
]
