"""Helper to combine growth and yield logs for multiple plants."""

from __future__ import annotations

import logging
from pathlib import Path

from plant_engine.utils import load_json, save_json

_LOGGER = logging.getLogger(__name__)


def export_all_growth_yield(base_dir: Path | None = None) -> dict[str, list]:
    """Return consolidated growth/yield logs from ``base_dir``."""

    if base_dir is None:
        base_dir = Path.cwd() / "analytics"
        if not base_dir.is_dir():
            base_dir = Path(__file__).parent
    if not base_dir.is_dir():
        _LOGGER.error("Analytics directory not found: %s", base_dir)
        return {}
    results = {}
    for file_path in base_dir.glob("*_growth_yield.json"):
        plant_id = file_path.name.replace("_growth_yield.json", "")
        data = load_json(file_path)
        if not isinstance(data, list):
            if data is not None:
                _LOGGER.error("Data in %s is not a list, skipping.", file_path)
            continue
        if len(data) == 0:
            _LOGGER.warning(
                "No growth yield data for plant %s (file is empty).", plant_id
            )
            continue
        results[plant_id] = data
    output_path = Path(__file__).parent / "all_plants_growth_yield.json"
    if save_json(output_path, results):
        _LOGGER.info("All plant growth yield data exported to %s", output_path)
    return results
