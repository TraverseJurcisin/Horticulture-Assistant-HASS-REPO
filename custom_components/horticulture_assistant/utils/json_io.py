import json
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)


def load_json(path: str | Path, default: Any | None = None) -> Any:
    """Load JSON data from ``path``. Return ``default`` on error."""
    try:
        with open(Path(path), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        _LOGGER.error("File not found: %s", path)
    except json.JSONDecodeError as err:
        _LOGGER.error("Invalid JSON in %s: %s", path, err)
    except Exception as err:  # pragma: no cover - unexpected errors
        _LOGGER.error("Error reading %s: %s", path, err)
    return default


def save_json(path: str | Path, data: Any, *, indent: int = 2) -> bool:
    """Write JSON data to ``path``. Return ``True`` on success."""
    try:
        with open(Path(path), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        return True
    except Exception as err:  # pragma: no cover - unexpected errors
        _LOGGER.error("Failed to write %s: %s", path, err)
    return False
