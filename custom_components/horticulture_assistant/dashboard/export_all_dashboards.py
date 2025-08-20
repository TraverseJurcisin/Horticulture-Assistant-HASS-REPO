# File: custom_components/horticulture_assistant/dashboard/export_all_dashboards.py

import os
import json
import logging
from pathlib import Path

from custom_components.horticulture_assistant.dashboard import grafana_exporter

_LOGGER = logging.getLogger(__name__)


def export_all_dashboards():
    """
    Compile dashboard data for all plant profiles into a single JSON.
    Scans the 'plants/' directory for profile files and aggregates their data.
    """
    base_dir = Path(os.getcwd()) / "plants"
    if not base_dir.is_dir():
        _LOGGER.error("Plant profiles directory not found: %s", base_dir)
        return {}
    results = {}
    # Iterate over all JSON files in the plants directory
    for file_path in base_dir.glob("*.json"):
        plant_id = file_path.stem
        try:
            data = grafana_exporter.export_grafana_data(plant_id)
        except Exception as e:
            _LOGGER.error("Skipping profile %s due to export error: %s.", plant_id, e)
            continue
        # Skip if no data returned for this plant
        if data is None:
            _LOGGER.warning("Skipping profile %s due to missing data.", plant_id)
            continue
        results[plant_id] = data
    # Write the combined dashboard data to a JSON file
    output_path = Path(__file__).parent / "all_plants_dashboard.json"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        _LOGGER.info("All plant dashboards exported to %s", output_path)
    except Exception as e:
        _LOGGER.error("Failed to write combined dashboard file: %s", e)
    return results
