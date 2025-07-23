"""Dataset discovery utilities.

This module exposes helpers for listing available JSON datasets bundled with
the project. A :class:`DatasetCatalog` dataclass manages dataset paths and uses
``lru_cache`` so repeated lookups avoid hitting the filesystem.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CATALOG_FILE = DATA_DIR / "dataset_catalog.json"

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

    base_dir: Path = DATA_DIR
    catalog_file: Path = CATALOG_FILE

    @lru_cache(maxsize=None)
    def list_datasets(self) -> List[str]:
        """Return relative paths of available JSON datasets."""

        datasets: List[str] = []
        for path in self.base_dir.rglob("*.json"):
            if path.name == self.catalog_file.name:
                continue
            datasets.append(path.relative_to(self.base_dir).as_posix())

        return sorted(datasets)

    @lru_cache(maxsize=None)
    def _load_catalog(self) -> Dict[str, str]:
        if self.catalog_file.exists():
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        return {}

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

