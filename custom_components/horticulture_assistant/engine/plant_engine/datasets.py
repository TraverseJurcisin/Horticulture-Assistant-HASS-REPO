"""Dataset discovery utilities.

This module exposes helpers for listing available datasets bundled with
the project (JSON or YAML). A :class:`DatasetCatalog` dataclass manages dataset paths and uses
``lru_cache`` so repeated lookups avoid hitting the filesystem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from . import utils
from .utils import (
    get_data_dir,
    get_extra_dirs,
    get_overlay_dir,
)

DATA_DIR = get_data_dir()
CATALOG_FILE = DATA_DIR / "dataset_catalog.json"

__all__ = [
    "DatasetCatalog",
    "list_datasets",
    "get_dataset_description",
    "list_dataset_info",
    "search_datasets",
    "list_datasets_by_category",
    "list_dataset_info_by_category",
    "get_dataset_path",
    "dataset_exists",
    "load_dataset_file",
    "validate_all_datasets",
    "refresh_datasets",
]


@dataclass(slots=True, frozen=True)
class DatasetCatalog:
    """Helper object for discovering bundled datasets."""

    base_dir: Path = field(default_factory=get_data_dir)
    extra_dirs: tuple[Path, ...] = field(default_factory=lambda: tuple(get_extra_dirs()))
    overlay_dir: Path | None = field(default_factory=get_overlay_dir)
    catalog_file: Path = field(default_factory=lambda: get_data_dir() / "dataset_catalog.json")

    @cache
    def paths(self) -> tuple[Path, ...]:
        """Return dataset search paths including overlay when set."""
        paths = [self.base_dir]

        local_temp = self.base_dir / "local/plants/temperature"
        if local_temp.exists():
            paths.append(local_temp)

        paths.extend(self.extra_dirs)
        if self.overlay_dir:
            paths.insert(0, self.overlay_dir)
        return tuple(paths)

    def _iter_paths(self) -> list[Path]:
        """Return search paths as a list for backward compatibility."""
        return list(self.paths())

    @cache
    def list_datasets(self) -> list[str]:
        """Return relative paths of available dataset files."""
        exts = {".json", ".yaml", ".yml"}
        found: set[str] = set()
        paths = self.paths()
        local_dir = self.base_dir / "local"
        for base in self._iter_paths():
            for p in base.rglob("*"):
                if p.suffix not in exts or p.name == "dataset_catalog.json":
                    continue
                rel = p.relative_to(base)
                if (
                    base == self.base_dir
                    and local_dir in paths
                    and rel.parts
                    and rel.parts[0] == "local"
                ):
                    # Skip duplicate entries when ``local`` is scanned separately
                    continue
                rel_path = rel.as_posix()
                found.add(rel_path)
                if (
                    len(rel.parts) >= 3
                    and rel.parts[0] == "plants"
                    and rel.parts[1] == "temperature"
                ):
                    found.add(rel.parts[-1])
        return sorted(found)

    @cache
    def _load_catalog(self) -> dict[str, str]:
        catalogs: dict[str, str] = {}
        for base in self._iter_paths():
            path = base / "dataset_catalog.json"
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                catalogs.update({str(k): str(v) for k, v in data.items()})
        return catalogs

    def get_description(self, name: str) -> str | None:
        """Return the human readable description for ``name`` if known."""

        return self._load_catalog().get(name)

    @cache
    def list_info(self) -> dict[str, str]:
        """Return mapping of dataset names to descriptions."""

        names = self.list_datasets()
        catalog = self._load_catalog()
        return {n: catalog.get(n, "") for n in names}

    def search(self, term: str) -> dict[str, str]:
        """Return datasets matching ``term`` in the name or description."""

        if not term:
            return {}

        term = term.lower()
        info = self.list_info()
        result: dict[str, str] = {}
        for name, desc in info.items():
            if term in name.lower() or term in desc.lower():
                result[name] = desc
        return result

    @cache
    def list_by_category(self) -> dict[str, list[str]]:
        """Return dataset names grouped by top-level directory."""

        categories: dict[str, list[str]] = {}
        for name in self.list_datasets():
            parts = name.split("/", 1)
            category = parts[0] if len(parts) > 1 else "root"
            categories.setdefault(category, []).append(name)

        for paths in categories.values():
            paths.sort()
        return categories

    @cache
    def find_path(self, name: str) -> Path | None:
        """Return absolute :class:`Path` to ``name`` if it exists."""

        for base in self._iter_paths():
            candidate = base / name
            if candidate.exists():
                return candidate
        return None

    @cache
    def load(self, name: str) -> object | None:
        """Return parsed data contents of ``name`` or ``None`` if missing.

        Results are cached to avoid repeated disk reads. Call
        :meth:`refresh` to clear the cache when underlying files may have
        changed.
        """

        path = self.find_path(name)
        if not path:
            return None
        return utils.load_data(str(path))

    def refresh(self) -> None:
        """Clear cached results so subsequent calls reload data."""

        self.list_datasets.cache_clear()
        self._load_catalog.cache_clear()
        self.list_info.cache_clear()
        self.list_by_category.cache_clear()
        self.load.cache_clear()
        self.paths.cache_clear()


DEFAULT_CATALOG = DatasetCatalog()


def list_datasets() -> list[str]:
    """Return relative paths of available dataset files."""

    return DEFAULT_CATALOG.list_datasets()


def get_dataset_description(name: str) -> str | None:
    """Return the human readable description for ``name`` if known."""

    return DEFAULT_CATALOG.get_description(name)


def list_dataset_info() -> dict[str, str]:
    """Return mapping of dataset names to descriptions."""

    return DEFAULT_CATALOG.list_info()


def search_datasets(term: str) -> dict[str, str]:
    """Return datasets matching ``term`` in the name or description."""

    return DEFAULT_CATALOG.search(term)


def list_datasets_by_category() -> dict[str, list[str]]:
    """Return dataset names grouped by top-level directory."""

    return DEFAULT_CATALOG.list_by_category()


def list_dataset_info_by_category() -> dict[str, dict[str, str]]:
    """Return dataset descriptions grouped by top-level directory."""

    by_cat = DEFAULT_CATALOG.list_by_category()
    info = DEFAULT_CATALOG.list_info()
    result: dict[str, dict[str, str]] = {}
    for cat, names in by_cat.items():
        result[cat] = {n: info.get(n, "") for n in names}
    return result


def get_dataset_path(name: str) -> Path | None:
    """Return absolute path to ``name`` if found in the catalog."""

    return DEFAULT_CATALOG.find_path(name)


def dataset_exists(name: str) -> bool:
    """Return ``True`` if ``name`` resolves to a dataset file."""

    return DEFAULT_CATALOG.find_path(name) is not None


def load_dataset_file(name: str) -> object | None:
    """Return parsed contents of ``name`` using the default catalog."""

    return DEFAULT_CATALOG.load(name)


def refresh_datasets() -> None:
    """Clear cached dataset and catalog results."""

    DEFAULT_CATALOG.refresh()
    # Also clear any cached dataset contents so reloading picks up changes
    from .utils import clear_dataset_cache

    clear_dataset_cache()


def validate_all_datasets() -> list[str]:
    """Return names of datasets that fail to load."""

    bad: list[str] = []
    for name in list_datasets():
        try:
            load_dataset_file(name)
        except Exception:
            bad.append(name)
    return bad
