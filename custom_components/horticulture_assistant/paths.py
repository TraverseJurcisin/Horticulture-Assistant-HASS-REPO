from __future__ import annotations
from pathlib import Path
from homeassistant.core import HomeAssistant

def ensure_local_data_paths(hass: HomeAssistant) -> None:
    """Ensure expected local data directories and files exist."""
    root = Path(hass.config.path())
    data_root = root / "data" / "local"
    plants_dir = data_root / "plants"
    data_root.mkdir(parents=True, exist_ok=True)
    plants_dir.mkdir(parents=True, exist_ok=True)
    zones_file = data_root / "zones.json"
    if not zones_file.exists() or zones_file.stat().st_size == 0:
        zones_file.write_text("{}", encoding="utf-8")
