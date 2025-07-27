"""Utility helpers for reading data files used across the plant engine."""

from __future__ import annotations

import json
import os
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Iterable, Union, IO, TextIO
from os import PathLike

import yaml

__all__ = [
    "load_json",
    "save_json",
    "load_data",
    "load_dataset",
    "lazy_dataset",
    "clear_dataset_cache",
    "dataset_paths",
    "dataset_search_paths",
    "get_data_dir",
    "get_pending_dir",
    "get_extra_dirs",
    "overlay_dir",
    "get_overlay_dir",
    "normalize_key",
    "list_dataset_entries",
    "parse_range",
    "deep_update",
    "stage_value",
    "load_stage_dataset_value",
]


PathType = Union[str, PathLike]


def _open_text(path: Path) -> TextIO:
    return open(path, "r", encoding="utf-8")


def load_json(path: PathType) -> Dict[str, Any]:
    """Return the parsed JSON contents of ``path``.

    A :class:`FileNotFoundError` is raised if the file does not exist and a
    :class:`ValueError` is raised when the contents cannot be decoded as JSON.
    The error message always includes the file path to aid debugging.
    """

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    try:
        with _open_text(p) as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {p}: {exc}") from exc


def load_data(path: PathType) -> Any:
    """Return the parsed contents of ``path`` supporting JSON or YAML."""

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)

    try:
        with _open_text(p) as f:
            if p.suffix.lower() in {".yaml", ".yml"}:
                return yaml.safe_load(f) or {}
            return json.load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {p}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {p}: {exc}") from exc


def save_json(path: PathType, data: Dict[str, Any]) -> bool:
    """Write ``data`` to ``path`` and return ``True`` on success."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True


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

# Cached dataset search path info
_PATH_CACHE: tuple[Path, ...] | None = None
_ENV_STATE: tuple[str | None, str | None] | None = None
# Cached overlay directory
_OVERLAY_CACHE: Path | None = None
_OVERLAY_ENV_VALUE: str | None = None

# Directory name for pending threshold changes relative to the data dir
PENDING_THRESHOLD_DIRNAME = "pending_thresholds"


def get_data_dir() -> Path:
    """Return base dataset directory honoring the ``HORTICULTURE_DATA_DIR`` env."""

    env = os.getenv("HORTICULTURE_DATA_DIR")
    return Path(env).expanduser() if env else DEFAULT_DATA_DIR


def get_pending_dir(base: str | Path | None = None) -> Path:
    """Return directory used for pending threshold changes."""

    base_dir = Path(base).expanduser() if base else get_data_dir()
    return base_dir / PENDING_THRESHOLD_DIRNAME


def overlay_dir() -> Path | None:
    """Return cached overlay directory defined via ``HORTICULTURE_OVERLAY_DIR``."""

    global _OVERLAY_CACHE, _OVERLAY_ENV_VALUE
    env = os.getenv(OVERLAY_ENV)
    if _OVERLAY_CACHE is None or _OVERLAY_ENV_VALUE != env:
        _OVERLAY_CACHE = Path(env).expanduser() if env else None
        _OVERLAY_ENV_VALUE = env
    return _OVERLAY_CACHE


def get_overlay_dir() -> Path | None:
    """Compatibility wrapper for :func:`overlay_dir`."""

    return overlay_dir()


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


def dataset_search_paths(include_overlay: bool = False) -> tuple[Path, ...]:
    """Return dataset search paths optionally including overlay first."""

    paths = []
    if include_overlay:
        ov = overlay_dir()
        if ov:
            paths.append(ov)
    paths.extend(dataset_paths())
    return tuple(paths)


@lru_cache(maxsize=None)
def dataset_file(filename: str) -> Path | None:
    """Return absolute path to ``filename`` if found in search paths.

    Searches the configured dataset directories and optional overlay once and
    caches the result for faster subsequent lookups. Use
    :func:`clear_dataset_cache` when environment variables change so the search
    path is refreshed.
    """

    for base in dataset_search_paths(include_overlay=True):
        path = base / filename
        if path.exists():
            return path

    return None


@lru_cache(maxsize=None)
def load_dataset(filename: str) -> Dict[str, Any]:
    """Return dataset ``filename`` merged with any overlay data."""

    data: Dict[str, Any] = {}
    paths = dataset_paths()
    for base in paths:
        path = base / filename
        if path.exists():
            extra = load_data(str(path))
            if isinstance(extra, dict) and isinstance(data, dict):
                deep_update(data, extra)
            else:
                data = extra

    overlay = overlay_dir()
    if overlay:
        overlay_path = overlay / filename
        if overlay_path.exists():
            extra = load_data(str(overlay_path))
            if isinstance(extra, dict) and isinstance(data, dict):
                deep_update(data, extra)
            else:
                data = extra

    return data


def lazy_dataset(filename: str):
    """Return a cached loader callable for dataset ``filename``."""

    @lru_cache(maxsize=None)
    def _loader():
        return load_dataset(filename)

    return _loader


def clear_dataset_cache() -> None:
    """Clear cached dataset results loaded via :func:`load_dataset`."""

    global _PATH_CACHE, _ENV_STATE, _OVERLAY_CACHE, _OVERLAY_ENV_VALUE
    load_dataset.cache_clear()
    dataset_file.cache_clear()
    _PATH_CACHE = None
    _ENV_STATE = None
    _OVERLAY_CACHE = None
    _OVERLAY_ENV_VALUE = None


def normalize_key(key: str) -> str:
    """Return ``key`` normalized for case-insensitive dataset lookups.

    The function uses :meth:`str.casefold` for robust case-insensitive
    matching and normalizes whitespace, hyphens and underscores to a single
    underscore character. Multiple adjacent separators are collapsed to avoid
    accidental duplication.
    """

    # ``casefold`` handles non ASCII characters better than ``lower``
    value = str(key).casefold()
    # Replace common separators with spaces then collapse to single underscores
    for sep in ("_", "-"):
        value = value.replace(sep, " ")
    parts = [p for p in value.strip().split() if p]
    return "_".join(parts)


def list_dataset_entries(dataset: Mapping[str, Any]) -> list[str]:
    """Return sorted top-level keys from a dataset mapping."""

    return sorted(str(k) for k in dataset.keys())


def parse_range(value: Iterable[float]) -> tuple[float, float] | None:
    """Return a normalized ``(low, high)`` tuple or ``None`` if invalid.

    ``value`` may be any iterable containing at least two numeric entries. The
    numbers are converted to ``float`` and sorted so that the lower value is
    returned first. If any conversion fails or either number is non-finite the
    function safely returns ``None`` instead of raising an exception.
    """

    try:
        iterator = iter(value)
        low = float(next(iterator))
        high = float(next(iterator))
        if not (math.isfinite(low) and math.isfinite(high)):
            return None
        if low > high:
            low, high = high, low
        return low, high
    except (StopIteration, TypeError, ValueError):
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

def load_stage_dataset_value(
    filename: str, plant_type: str, stage: str | None, default_key: str = "optimal"
) -> Any:
    """Return a stage value from ``filename`` for ``plant_type`` and ``stage``.

    Combines :func:`load_dataset` and :func:`stage_value` for convenience. If the
    dataset file does not exist or is not a mapping, ``None`` is returned.
    """
    data = load_dataset(filename)
    if not isinstance(data, Mapping):
        return None
    return stage_value(data, plant_type, stage, default_key)

