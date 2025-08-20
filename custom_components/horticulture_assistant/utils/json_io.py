"""Lightweight JSON read/write helpers for profile management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_json(path: str | Path) -> Dict[str, Any]:
    """Return the parsed JSON contents of ``path``."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str | Path, data: Dict[str, Any]) -> bool:
    """Write ``data`` to ``path`` in JSON format."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return True


__all__ = ["load_json", "save_json"]
