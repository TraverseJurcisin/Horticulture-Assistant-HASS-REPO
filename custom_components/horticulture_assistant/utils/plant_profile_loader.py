"""Helpers for loading structured plant profile data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from functools import lru_cache

# Attempt to import yaml for YAML support
try:
    import yaml
except ImportError:
    yaml = None

_LOGGER = logging.getLogger(__name__)

# Default directory containing individual plant profiles
DEFAULT_BASE_DIR = Path("plants")

REQUIRED_THRESHOLD_KEYS = {"light", "temperature", "EC"}
REQUIRED_STAGE_KEY = "stage_duration"

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

    def _load_json(fp: Path) -> dict:
        with open(fp, "r", encoding="utf-8") as f:
            return json.load(f) or {}

    def _load_yaml(fp: Path) -> dict:
        content = fp.read_text(encoding="utf-8")
        if yaml is not None:
            return yaml.safe_load(content) or {}

        # Very small fallback parser supporting the limited syntax used in tests
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

    try:
        if ext == ".json":
            data = _load_json(path_obj)
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
    directory = Path(base_dir) if base_dir else DEFAULT_BASE_DIR
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