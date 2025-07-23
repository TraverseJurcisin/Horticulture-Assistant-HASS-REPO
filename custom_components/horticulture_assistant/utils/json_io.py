"""Lightweight helpers for JSON file operations.

This module previously re-implemented basic ``json.load`` and ``json.dump``
logic in several places across the code base.  To reduce repetition we now
delegate to the existing helpers in :mod:`plant_engine.utils` while preserving
the simple error handling behaviour expected by callers.
"""

import json
import logging
from pathlib import Path
from typing import Any

from plant_engine.utils import load_json as _load_json, save_json as _save_json

_LOGGER = logging.getLogger(__name__)


def load_json(path: str | Path, default: Any | None = None) -> Any:
    """Load JSON data from ``path``.

    Any errors are logged and ``default`` is returned instead of raising
    exceptions.  This mirrors the behaviour of the previous implementation
    while relying on :func:`plant_engine.utils.load_json` for the heavy
    lifting.
    """

    try:
        return _load_json(str(path))
    except Exception as err:  # pragma: no cover - unexpected errors
        _LOGGER.error("Error reading %s: %s", path, err)
        return default


def save_json(path: str | Path, data: Any, *, indent: int = 2) -> bool:
    """Write JSON data to ``path``. Return ``True`` on success."""

    try:
        if indent == 2:
            _save_json(str(path), data)
        else:  # honour custom indentation
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(Path(path), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=indent)
        return True
    except Exception as err:  # pragma: no cover - unexpected errors
        _LOGGER.error("Failed to write %s: %s", path, err)
        return False

