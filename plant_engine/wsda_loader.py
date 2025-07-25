import os
import json
from pathlib import Path
from typing import Iterator, Dict, Any

import pandas as pd

WSDA_INDEX_DIR = Path(os.getenv("WSDA_INDEX_DIR", "data/index_sharded"))
WSDA_DETAIL_DIR = Path(os.getenv("WSDA_DETAIL_DIR", "data/detail"))


def stream_index() -> Iterator[Dict[str, Any]]:
    """Yield product index records from all shards."""
    if not WSDA_INDEX_DIR.exists():
        return iter(())
    for path in sorted(WSDA_INDEX_DIR.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)


def load_index_df() -> pd.DataFrame:
    """Return the full index as a :class:`pandas.DataFrame`."""
    return pd.DataFrame(stream_index())


def load_detail(product_id: str) -> Dict[str, Any]:
    """Return detailed record for ``product_id``.

    Raises
    ------
    FileNotFoundError
        If the corresponding detail file does not exist.
    """
    prefix = product_id[:2]
    path = WSDA_DETAIL_DIR / prefix / f"{product_id}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
