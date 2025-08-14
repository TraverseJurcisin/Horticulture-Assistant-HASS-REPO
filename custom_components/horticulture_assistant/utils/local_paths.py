from __future__ import annotations

from homeassistant.core import HomeAssistant
from pathlib import Path
import json


def normalize_local_paths(hass: HomeAssistant) -> None:
    root = Path(hass.config.path("custom_components"))
    data_root = root.parents[1] / "data" / "local"
    plants_dir = data_root / "plants"
    zones_file = data_root / "zones.json"
    plants_dir.mkdir(parents=True, exist_ok=True)
    if not zones_file.exists():
        zones_file.write_text(json.dumps({}), encoding="utf-8")
