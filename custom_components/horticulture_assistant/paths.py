from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from homeassistant.core import HomeAssistant


_LOGGER = logging.getLogger(__name__)


def _file_is_empty(path: Path) -> bool:
    """Return True if file doesn't exist or is empty."""
    return not path.exists() or path.stat().st_size == 0


async def ensure_local_data_paths(hass: HomeAssistant) -> None:
    """Ensure expected local data directories and files exist without blocking."""
    root = Path(hass.config.path())
    data_root = root / "data" / "local"
    plants_dir = data_root / "plants"

    try:
        for dir_path in (data_root, plants_dir):
            await hass.async_add_executor_job(
                partial(dir_path.mkdir, parents=True, exist_ok=True)
            )

        zones_file = data_root / "zones.json"
        is_empty = await hass.async_add_executor_job(_file_is_empty, zones_file)
        if is_empty:
            await hass.async_add_executor_job(
                zones_file.write_text, "{}", "utf-8"
            )
    except OSError as err:  # file system errors
        _LOGGER.error("Failed to ensure local data paths: %s", err)
