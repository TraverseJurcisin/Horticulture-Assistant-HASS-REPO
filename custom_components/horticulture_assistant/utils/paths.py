from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant


def _mkdirs_and_touch_sync(cfg_dir: str) -> None:
    root = Path(cfg_dir)
    data_root = root / "data" / "local"
    plants_dir = data_root / "plants"
    data_root.mkdir(parents=True, exist_ok=True)
    plants_dir.mkdir(parents=True, exist_ok=True)
    (data_root / "zones.json").touch(exist_ok=True)


async def ensure_local_data_paths(hass: HomeAssistant) -> None:
    """Ensure expected local data directories and files exist without blocking."""
    await hass.async_add_executor_job(_mkdirs_and_touch_sync, hass.config.path())
