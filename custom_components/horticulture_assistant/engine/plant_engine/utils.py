"""Utility helpers for reading datasets and parsing horticulture values."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Iterable, Mapping
from functools import cache, lru_cache
from os import PathLike
from pathlib import Path
from typing import Any, TextIO, Union

import yaml

__all__ = [
    "load_json",
    "save_json",
    "load_data",
    "load_dataset",
    "async_load_dataset",
    "load_datasets",
    "lazy_dataset",
    "load_dataset_df",
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
    "clean_float_map",
    "deep_update",
    "stage_value",
    "load_stage_dataset_value",
    "list_dataset_files",
]

_RANGE_PATTERN = re.compile(r"(?<!\d)[-+]?\d*\.?\d+(?:e[-+]?\d+)?")

PathType = Union[str, PathLike]


def _open_text(path: Path) -> TextIO:
    return open(path, encoding="utf-8")


def load_json(path: PathType) -> dict[str, Any]:
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


def save_json(path: PathType, data: dict[str, Any]) -> bool:
    """Write ``data`` to ``path`` and return ``True`` on success."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True


def deep_update(base: dict[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``other`` into ``base`` and return ``base``."""

    for key, value in other.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, Mapping):
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
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
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

    The base ``data`` directory is always included and the ``data/local``
    subfolder is added automatically when it exists so user-provided files can
    coexist with bundled datasets. Results are cached but automatically
    refreshed if the relevant environment variables change. This avoids
    repeated environment lookups while still allowing tests or applications to
    modify the dataset paths on the fly.
    """

    global _PATH_CACHE, _ENV_STATE
    env_state = (os.getenv("HORTICULTURE_DATA_DIR"), os.getenv(EXTRA_ENV))
    if _PATH_CACHE is None or _ENV_STATE != env_state:
        base = get_data_dir()
        extras = get_extra_dirs()

        local_temp = base / "local/plants/temperature"
        paths = [base]
        if local_temp.exists():
            paths.append(local_temp)

        paths.extend(extras)
        _PATH_CACHE = tuple(paths)
        _ENV_STATE = env_state
    return _PATH_CACHE


def dataset_search_paths(include_overlay: bool = False) -> tuple[Path, ...]:
    """Return dataset search paths optionally including the overlay directory."""

    env_state = (
        os.getenv("HORTICULTURE_DATA_DIR"),
        os.getenv(EXTRA_ENV),
        os.getenv(OVERLAY_ENV),
    )
    return _dataset_search_paths(include_overlay, *env_state)


@cache
def _dataset_search_paths(
    include_overlay: bool,
    data_env: str | None,
    extra_env: str | None,
    overlay_env: str | None,
) -> tuple[Path, ...]:
    paths = []
    if include_overlay:
        ov = overlay_dir()
        if ov:
            paths.append(ov)
    paths.extend(dataset_paths())
    return tuple(paths)


@cache
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
        alt = base / "plants" / "temperature" / filename
        if alt.exists():
            return alt

    return None


@cache
def load_dataset(filename: str) -> dict[str, Any]:
    """Return dataset ``filename`` merged with any overlay data."""

    data: dict[str, Any] = {}
    paths = dataset_paths()
    for base in paths:
        path = base / filename
        if path.exists():
            extra = load_data(str(path))
            if isinstance(extra, dict) and isinstance(data, dict):
                deep_update(data, extra)
            else:
                data = extra
            continue
        alt = base / "plants" / "temperature" / filename
        if alt.exists():
            extra = load_data(str(alt))
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


async def async_load_dataset(filename: str) -> dict[str, Any]:
    """Asynchronously load dataset ``filename`` in a thread."""

    import asyncio

    return await asyncio.to_thread(load_dataset, filename)


def lazy_dataset(filename: str):
    """Return a callable that loads ``filename`` with simple caching.

    The loader clears global dataset caches before reading the file so that
    each call reflects the current dataset environment. The returned function
    is wrapped with :func:`functools.lru_cache` to provide a ``cache_clear``
    attribute used heavily throughout the test suite to reset state between
    tests.
    """

    @lru_cache(maxsize=1)
    def _loader() -> dict[str, Any]:
        clear_dataset_cache()
        return load_dataset(filename)

    return _loader


def load_dataset_df(filename: str) -> pd.DataFrame:
    """Return dataset ``filename`` as a :class:`pandas.DataFrame`.

    JSON/YAML files are loaded via :func:`load_dataset`. CSV/TSV files are read
    directly if located in one of the configured dataset directories.
    Dictionaries are treated as row mappings and lists as row sequences.
    Unsupported data structures raise ``ValueError``.
    """

    import pandas as pd

    path = dataset_file(filename)
    if path and path.suffix.lower() in {".csv", ".tsv"}:
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        return pd.read_csv(path, sep=sep)

    data = load_dataset(filename)
    if isinstance(data, Mapping):
        return pd.DataFrame.from_dict(data, orient="index")
    if isinstance(data, list):
        return pd.DataFrame(data)
    raise ValueError(f"Dataset {filename} is not tabular")


@cache
def load_datasets(*filenames: str) -> dict[str, dict[str, Any]]:
    """Return multiple datasets keyed by filename.

    Each file is loaded via :func:`load_dataset` and the results are cached to
    minimize disk access when called repeatedly.
    """

    data: dict[str, dict[str, Any]] = {}
    for name in filenames:
        data[name] = load_dataset(name)
    return data


def clear_dataset_cache() -> None:
    """Clear cached dataset results loaded via :func:`load_dataset`."""

    global _PATH_CACHE, _ENV_STATE, _OVERLAY_CACHE, _OVERLAY_ENV_VALUE
    load_dataset.cache_clear()
    dataset_file.cache_clear()
    _dataset_search_paths.cache_clear()
    _PATH_CACHE = None
    _ENV_STATE = None
    _OVERLAY_CACHE = None
    _OVERLAY_ENV_VALUE = None
    list_dataset_files.cache_clear()


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


def parse_range(value: Iterable[float] | str) -> tuple[float, float] | None:
    """Return a normalized ``(low, high)`` tuple or ``None`` if invalid.

    ``value`` may be an iterable containing numeric entries or a string in the
    form ``"low-high"``. The first two numbers found are converted to ``float``
    and sorted so that the lower value is returned first. If conversion fails or
    either number is non-finite the function safely returns ``None`` instead of
    raising an exception.
    """

    numbers: list[float] = []
    if isinstance(value, str):
        cleaned = re.sub(r"(?i)\bto\b", " ", value)
        for match in _RANGE_PATTERN.finditer(cleaned):
            try:
                numbers.append(float(match.group()))
            except ValueError:
                continue
            if len(numbers) == 2:
                break
    else:
        try:
            iterator = iter(value)
        except TypeError:
            return None

        for item in iterator:
            try:
                numbers.append(float(item))
            except (TypeError, ValueError):
                continue
            if len(numbers) == 2:
                break

    if len(numbers) < 2:
        return None

    low, high = numbers[0], numbers[1]
    if not (math.isfinite(low) and math.isfinite(high)):
        return None
    if low > high:
        low, high = high, low
    return low, high


def clean_float_map(data: Mapping[str, Any]) -> dict[str, float]:
    """Return mapping with float values ignoring invalid entries."""

    result: dict[str, float] = {}
    for key, value in data.items():
        try:
            num = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(num) and num > 0:
            result[key] = num
    return result


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


@cache
def list_dataset_files() -> list[str]:
    """Return alphabetically sorted dataset files available in search paths.

    Results are cached to avoid repeated directory scans which can be
    expensive on slower storage. Call :func:`clear_dataset_cache` when the
    underlying files may have changed so the cache is refreshed.
    """

    files: set[str] = set()
    for base in dataset_search_paths(include_overlay=True):
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if (
                path.suffix.lower() in {".json", ".yaml", ".yml"}
                and path.is_file()
                and path.name != "dataset_catalog.json"
            ):
                files.add(path.relative_to(base).as_posix())
    return sorted(files)
