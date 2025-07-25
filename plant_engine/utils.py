"""Utility helpers for reading data files used across the plant engine."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Iterable

__all__ = [
    "load_json",
    "save_json",
    "load_dataset",
    "clear_dataset_cache",
    "dataset_paths",
    "get_data_dir",
    "get_extra_dirs",
    "get_overlay_dir",
    "get_plants_dir",
    "normalize_key",
    "list_dataset_entries",
    "parse_range",
    "deep_update",
    "stage_value",
]


def load_json(path: str) -> Dict[str, Any]:
    """Return the parsed JSON contents of ``path``.

    A :class:`FileNotFoundError` is raised if the file does not exist and a
    :class:`ValueError` is raised when the contents cannot be decoded as JSON.
    The error message always includes the file path to aid debugging.
    """

    if not os.path.exists(path):
        raise FileNotFoundError(path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def save_json(path: str, data: Dict[str, Any]) -> None:
    """Write a dictionary to a JSON file, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def deep_update(base: Dict[str, Any], other: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``other`` into ``base`` and return ``base``."""

    for key, value in other.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, Mapping)
        ):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


# Default data directory is the repository ``data`` folder. It can be
# overridden using ``HORTICULTURE_DATA_DIR``. An optional overlay directory
# ``HORTICULTURE_OVERLAY_DIR`` can hold user-provided files that merge with
# the defaults. Additional directories may be specified via the
# ``HORTICULTURE_EXTRA_DATA_DIRS`` environment variable as a
# ``os.pathsep``-separated list. These paths are merged in order after the
# default data directory but before the overlay directory. This allows
# extending or overriding individual datasets without copying the entire
# directory hierarchy.
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OVERLAY_ENV = "HORTICULTURE_OVERLAY_DIR"
EXTRA_ENV = "HORTICULTURE_EXTRA_DATA_DIRS"

# Optional base directory for plant profiles.
PLANTS_ENV = "HORTICULTURE_PLANTS_DIR"
DEFAULT_PLANTS_DIR = Path("plants")

# Cached dataset search path info
_PATH_CACHE: tuple[Path, ...] | None = None
_ENV_STATE: tuple[str | None, str | None] | None = None


def get_data_dir() -> Path:
    """Return base dataset directory honoring the ``HORTICULTURE_DATA_DIR`` env."""

    env = os.getenv("HORTICULTURE_DATA_DIR")
    return Path(env).expanduser() if env else DEFAULT_DATA_DIR


def get_overlay_dir() -> Path | None:
    """Return optional overlay directory defined via ``HORTICULTURE_OVERLAY_DIR``."""

    env = os.getenv(OVERLAY_ENV)
    return Path(env).expanduser() if env else None


def get_extra_dirs() -> tuple[Path, ...]:
    """Return additional dataset directories from ``HORTICULTURE_EXTRA_DATA_DIRS``."""

    env = os.getenv(EXTRA_ENV)
    if not env:
        return ()
    dirs: list[Path] = []
    for part in env.split(os.pathsep):
        path = Path(part).expanduser()
        if path.is_dir():
            dirs.append(path)
    return tuple(dirs)


def get_plants_dir() -> Path:
    """Return base directory for plant profiles."""

    env = os.getenv(PLANTS_ENV)
    return Path(env).expanduser() if env else DEFAULT_PLANTS_DIR


def dataset_paths() -> tuple[Path, ...]:
    """Return directories searched when loading datasets.

    Results are cached but automatically refreshed if the relevant
    environment variables change. This avoids repeated environment lookups
    while still allowing tests or applications to modify the dataset paths
    on the fly.
    """

    global _PATH_CACHE, _ENV_STATE
    env_state = (os.getenv("HORTICULTURE_DATA_DIR"), os.getenv(EXTRA_ENV))
    if _PATH_CACHE is None or _ENV_STATE != env_state:
        base = get_data_dir()
        extras = get_extra_dirs()
        _PATH_CACHE = (base, *extras)
        _ENV_STATE = env_state
    return _PATH_CACHE


@lru_cache(maxsize=None)
def load_dataset(filename: str) -> Dict[str, Any]:
    """Return dataset ``filename`` merged with any overlay data."""

    data: Dict[str, Any] = {}
    paths = dataset_paths()
    for base in paths:
        path = base / filename
        if path.exists():
            extra = load_json(str(path))
            if isinstance(extra, dict) and isinstance(data, dict):
                deep_update(data, extra)
            else:
                data = extra

    overlay = get_overlay_dir()
    if overlay:
        overlay_path = overlay / filename
        if overlay_path.exists():
            extra = load_json(str(overlay_path))
            if isinstance(extra, dict) and isinstance(data, dict):
                deep_update(data, extra)
            else:
                data = extra

    return data


def clear_dataset_cache() -> None:
    """Clear cached dataset results loaded via :func:`load_dataset`."""

    global _PATH_CACHE, _ENV_STATE
    load_dataset.cache_clear()
    _PATH_CACHE = None
    _ENV_STATE = None


def normalize_key(key: str) -> str:
    """Return ``key`` normalized for case-insensitive dataset lookups."""
    return str(key).lower().replace(" ", "_")


def list_dataset_entries(dataset: Mapping[str, Any]) -> list[str]:
    """Return sorted top-level keys from a dataset mapping."""

    return sorted(str(k) for k in dataset.keys())


def parse_range(value: Iterable[float]) -> tuple[float, float] | None:
    """Return a normalized ``(min, max)`` tuple or ``None`` if invalid.

    ``value`` may be any iterable with at least two numeric entries. Values are
    cast to ``float`` and returned as a two-item tuple. If the input cannot be
    interpreted as a pair of numbers, ``None`` is returned instead of raising an
    exception.
    """

    try:
        low, high = value
        return float(low), float(high)
    except (TypeError, ValueError, Exception):
        return None


def stage_value(
    dataset: Mapping[str, Any],
    plant_type: str,
    stage: str | None,
    default_key: str = "optimal",
) -> Any:
    """Return a stage specific value from ``dataset`` with fallback."""

    plant = dataset.get(normalize_key(plant_type), {})
    if stage:
        value = plant.get(normalize_key(stage))
        if value is not None:
            return value
    return plant.get(default_key)
