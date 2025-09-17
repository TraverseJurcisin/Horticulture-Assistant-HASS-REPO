"""Helpers for loading fertilizer dataset shards."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

from .utils import get_data_dir

REPO_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "fertilizers"
REPO_INDEX_DIR = REPO_DATA_DIR / "index_sharded"
REPO_DETAIL_DIR = REPO_DATA_DIR / "detail"


FERTILIZER_DATASET_ROOT = Path(os.getenv("FERTILIZER_DATASET_ROOT", get_data_dir() / "fertilizer_dataset_sharded"))
FERTILIZER_DATASET_INDEX_DIR = Path(os.getenv("FERTILIZER_DATASET_INDEX_DIR", FERTILIZER_DATASET_ROOT / "index_sharded"))
if not FERTILIZER_DATASET_INDEX_DIR.exists() and REPO_INDEX_DIR.exists():
    FERTILIZER_DATASET_INDEX_DIR = REPO_INDEX_DIR
FERTILIZER_DATASET_DETAIL_DIR = Path(os.getenv("FERTILIZER_DATASET_DETAIL_DIR", FERTILIZER_DATASET_ROOT / "detail"))
if not FERTILIZER_DATASET_DETAIL_DIR.exists() and REPO_DETAIL_DIR.exists():
    FERTILIZER_DATASET_DETAIL_DIR = REPO_DETAIL_DIR


def stream_index() -> Iterator[dict[str, Any]]:
    """Yield product index records from all shards."""
    if not FERTILIZER_DATASET_INDEX_DIR.exists():
        return iter(())
    for path in sorted(FERTILIZER_DATASET_INDEX_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


def load_index_df():  # type: ignore[return-type]
    """Return the full index as a :class:`pandas.DataFrame`.

    Pandas is an optional dependency; a clear error is raised if it is missing.
    """

    if pd is None:  # pragma: no cover - runtime guard
        raise RuntimeError(
            "pandas is required for load_index_df(); install pandas to use this helper"
        )
    return pd.DataFrame(stream_index())


def load_detail(product_id: str) -> dict[str, Any]:
    """Return detailed record for ``product_id``.

    Raises
    ------
    FileNotFoundError
        If the corresponding detail file does not exist.
    """
    prefix = product_id[:2]
    path = FERTILIZER_DATASET_DETAIL_DIR / prefix / f"{product_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
