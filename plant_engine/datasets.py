"""Dataset discovery utilities.

This module exposes helpers for listing available JSON datasets bundled with
the project. A :class:`DatasetCatalog` dataclass manages dataset paths and uses
``lru_cache`` so repeated lookups avoid hitting the filesystem.  It now honors
the ``HORTICULTURE_DATA_DIR``, ``HORTICULTURE_EXTRA_DATA_DIRS`` and
``HORTICULTURE_OVERLAY_DIR`` environment variables in the same manner as
``plant_engine.utils.load_dataset`` so custom data locations are discovered
automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from .utils import _data_dir, _extra_dirs, _overlay_dir, load_json, deep_update

CATALOG_FILENAME = "dataset_catalog.json"

__all__ = [
    "DatasetCatalog",
    "list_datasets",
    "get_dataset_description",
    "list_dataset_info",
    "search_datasets",
    "list_datasets_by_category",
]


@dataclass(slots=True, frozen=True)
class DatasetCatalog:
    """Helper object for discovering bundled datasets."""

    base_dir: Path = field(default_factory=_data_dir)
    extra_dirs: tuple[Path, ...] = field(default_factory=lambda: tuple(_extra_dirs()))
    overlay_dir: Path | None = field(default_factory=_overlay_dir)
    catalog_file_name: str = CATALOG_FILENAME

    @lru_cache(maxsize=None)
    def list_datasets(self) -> List[str]:
        """Return relative paths of available JSON datasets."""

        datasets: Dict[str, Path] = {}
        search_dirs = [self.base_dir, *self.extra_dirs]
        for directory in search_dirs:
            if not directory.is_dir():
                continue
            for path in directory.rglob("*.json"):
                if path.name == self.catalog_file_name:
                    continue
                datasets[path.relative_to(directory).as_posix()] = path

        if self.overlay_dir and self.overlay_dir.is_dir():
            for path in self.overlay_dir.rglob("*.json"):
                if path.name == self.catalog_file_name:
                    continue
                datasets[path.relative_to(self.overlay_dir).as_posix()] = path

        return sorted(datasets.keys())

    @lru_cache(maxsize=None)
    def _load_catalog(self) -> Dict[str, str]:
        data: Dict[str, str] = {}
        search_dirs = [self.base_dir, *self.extra_dirs]
        for directory in search_dirs:
            path = directory / self.catalog_file_name
            if path.exists():
                extra = load_json(str(path))
                if isinstance(extra, dict):
                    deep_update(data, {str(k): str(v) for k, v in extra.items()})

        if self.overlay_dir:
            path = self.overlay_dir / self.catalog_file_name
            if path.exists():
                extra = load_json(str(path))
                if isinstance(extra, dict):
                    deep_update(data, {str(k): str(v) for k, v in extra.items()})

        return data

    def get_description(self, name: str) -> str | None:
        """Return the human readable description for ``name`` if known."""

        return self._load_catalog().get(name)

    @lru_cache(maxsize=None)
    def list_info(self) -> Dict[str, str]:
        """Return mapping of dataset names to descriptions."""

        names = self.list_datasets()
        catalog = self._load_catalog()
        return {n: catalog.get(n, "") for n in names}

    def search(self, term: str) -> Dict[str, str]:
        """Return datasets matching ``term`` in the name or description."""

        if not term:
            return {}

        term = term.lower()
        info = self.list_info()
        result: Dict[str, str] = {}
        for name, desc in info.items():
            if term in name.lower() or term in desc.lower():
                result[name] = desc
        return result

    @lru_cache(maxsize=None)
    def list_by_category(self) -> Dict[str, List[str]]:
        """Return dataset names grouped by top-level directory."""

        categories: Dict[str, List[str]] = {}
        for name in self.list_datasets():
            parts = name.split("/", 1)
            category = parts[0] if len(parts) > 1 else "root"
            categories.setdefault(category, []).append(name)

        for paths in categories.values():
            paths.sort()
        return categories


DEFAULT_CATALOG = DatasetCatalog()


def list_datasets() -> List[str]:
    """Return relative paths of available JSON datasets."""

    return DEFAULT_CATALOG.list_datasets()


def get_dataset_description(name: str) -> str | None:
    """Return the human readable description for ``name`` if known."""

    return DEFAULT_CATALOG.get_description(name)


def list_dataset_info() -> Dict[str, str]:
    """Return mapping of dataset names to descriptions."""

    return DEFAULT_CATALOG.list_info()


def search_datasets(term: str) -> Dict[str, str]:
    """Return datasets matching ``term`` in the name or description."""

    return DEFAULT_CATALOG.search(term)


def list_datasets_by_category() -> Dict[str, List[str]]:
    """Return dataset names grouped by top-level directory."""

    return DEFAULT_CATALOG.list_by_category()

