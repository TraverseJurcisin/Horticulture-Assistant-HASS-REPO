import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean

from custom_components.horticulture_assistant.utils.path_utils import (
    data_path,
    plants_path,
)
from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    load_plant_profile,
)

from ..utils.json_io import load_json, save_json

_LOGGER = logging.getLogger(__name__)


def _load_log(log_path):
    try:
        return load_json(str(log_path))
    except Exception as e:
        _LOGGER.warning("Failed to read %s: %s", log_path, e)
        return []


def _filter_last_24h(entries):
    now = datetime.now(UTC)
    threshold = now - timedelta(days=1)
    return [
        e
        for e in entries
        if "timestamp" in e and datetime.fromisoformat(e["timestamp"]) >= threshold
    ]


def build_daily_report(
    plant_id: str,
    base_path: str | None = None,
    output_path: str | None = None,
) -> dict:
    """Build and save a 24 hour summary report for ``plant_id``.

    ``base_path`` and ``output_path`` default to the configured ``plants`` and
    ``data/daily_reports`` directories, respectively.
    """
    if base_path is None:
        base_path = plants_path(None)
    if output_path is None:
        output_path = data_path(None, "daily_reports")

    plant_dir = Path(base_path) / plant_id
    report = {
        "plant_id": plant_id,
        "lifecycle_stage": None,
        "nutrient_thresholds": {},
        "irrigation_summary": {},
        "nutrient_summary": {},
        "sensor_summary": {},
        "visual_summary": {},
        "yield": None,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Load profile and current thresholds
    profile = load_plant_profile(plant_id, base_path)
    if isinstance(profile, dict):
        profile_data = profile.get("profile_data", {})
    else:
        profile_data = profile.profile_data
    stage_data = profile_data.get("stage", {})
    thresholds = profile_data.get("thresholds", {})

    report["lifecycle_stage"] = stage_data.get("current", "unknown")
    report["nutrient_thresholds"] = thresholds

    # Load log files
    irrigation = _filter_last_24h(_load_log(plant_dir / "irrigation_log.json"))
    nutrients = _filter_last_24h(_load_log(plant_dir / "nutrient_application_log.json"))
    sensors = _filter_last_24h(_load_log(plant_dir / "sensor_reading_log.json"))
    visuals = _filter_last_24h(_load_log(plant_dir / "visual_inspection_log.json"))
    yields = _filter_last_24h(_load_log(plant_dir / "yield_tracking_log.json"))

    # Irrigation Summary
    if irrigation:
        total_volume = sum(e.get("volume_applied_ml", 0) for e in irrigation)
        report["irrigation_summary"] = {
            "events": len(irrigation),
            "total_volume_ml": total_volume,
            "methods": list({e.get("method") for e in irrigation}),
        }

    # Nutrient Summary
    if nutrients:
        applied = {}
        for e in nutrients:
            formulation = e.get("nutrient_formulation", {})
            for k, v in formulation.items():
                applied[k] = applied.get(k, 0) + v
        report["nutrient_summary"] = applied

    # Sensor Summary
    sensor_types = {}
    for e in sensors:
        stype = e.get("sensor_type")
        if stype and "value" in e:
            sensor_types.setdefault(stype, []).append(e["value"])
    report["sensor_summary"] = {
        stype: round(mean(vals), 2) for stype, vals in sensor_types.items() if vals
    }

    # Visual Summary
    if visuals:
        report["visual_summary"] = visuals[-1]  # most recent visual inspection

    # Yield
    if yields:
        report["yield"] = yields[-1].get("yield_quantity")

    # Ensure output path exists
    Path(output_path).mkdir(parents=True, exist_ok=True)
    out_file = Path(output_path) / f"{plant_id}_{datetime.now(UTC).date()}.json"
    try:
        save_json(str(out_file), report)
        _LOGGER.info("Saved daily report for %s to %s", plant_id, out_file)
    except Exception as e:
        _LOGGER.error("Failed to write report for %s: %s", plant_id, e)

    return report
