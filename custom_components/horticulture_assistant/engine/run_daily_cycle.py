"""Daily report generation for plant profiles.

This module summarizes the previous day's irrigation, nutrient applications,
sensor readings and growth metrics into a JSON report that can be consumed by
other automations or dashboards.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    load_profile_by_id,
)
from plant_engine.environment_manager import compare_environment
from plant_engine.utils import load_dataset

_LOGGER = logging.getLogger(__name__)

def _load_log(log_path):
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        _LOGGER.info(f"Log file not found: {log_path}")
        return []
    except Exception as e:
        _LOGGER.warning(f"Failed to read {log_path}: {e}")
        return []

def _filter_last_24h(entries):
    now = datetime.utcnow()
    cutoff = now - timedelta(days=1)
    recent = []
    for e in entries:
        ts = e.get('timestamp')
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts)
        except Exception:
            # If timestamp format is not ISO, skip this entry
            continue
        if t >= cutoff:
            recent.append(e)
    return recent

def run_daily_cycle(plant_id: str, base_path: str = "plants", output_path: str = "data/daily_reports") -> dict:
    """Run the daily processing cycle for a given plant and produce a daily report."""
    plant_dir = Path(base_path) / plant_id
    report = {
        "plant_id": plant_id,
        "lifecycle_stage": "unknown",
        "thresholds": {},
        "irrigation_summary": {},
        "nutrient_summary": {},
        "sensor_summary": {},
        "environment_comparison": {},
        "pest_actions": {},
        "disease_actions": {},
        "root_zone": {},
        "stage_info": {},
        "yield": None,
        "timestamp": datetime.utcnow().isoformat()
    }
    # Load plant profile (structured data)
    profile = load_profile_by_id(plant_id, base_dir=base_path)
    if not profile:
        _LOGGER.error("No profile found for plant_id %s", plant_id)
        return report
    # Determine current lifecycle stage
    general = profile.get("general", {})
    stage_name = general.get("lifecycle_stage") or general.get("stage")
    if stage_name:
        report["lifecycle_stage"] = stage_name
    # Get current thresholds from profile
    thresholds = profile.get("thresholds", {})
    report["thresholds"] = thresholds
    # Load last 24h logs for irrigation, nutrients, sensors, visuals, yield
    irrigation_entries = _filter_last_24h(_load_log(plant_dir / "irrigation_log.json"))
    nutrient_entries = _filter_last_24h(_load_log(plant_dir / "nutrient_application_log.json"))
    sensor_entries = _filter_last_24h(_load_log(plant_dir / "sensor_reading_log.json"))
    visual_entries = _filter_last_24h(_load_log(plant_dir / "visual_inspection_log.json"))
    yield_entries = _filter_last_24h(_load_log(plant_dir / "yield_tracking_log.json"))
    # Summarize irrigation events (24h)
    if irrigation_entries:
        total_volume = sum(e.get("volume_applied_ml", 0) for e in irrigation_entries)
        methods = {e.get("method") for e in irrigation_entries if e.get("method")}
        report["irrigation_summary"] = {
            "events": len(irrigation_entries),
            "total_volume_ml": total_volume,
            "methods": list(methods)
        }
    # Summarize nutrient applications (aggregate nutrients applied in 24h)
    if nutrient_entries:
        nutrient_totals = {}
        for entry in nutrient_entries:
            formulation = entry.get("nutrient_formulation", {})
            for nutrient, amount in formulation.items():
                nutrient_totals[nutrient] = nutrient_totals.get(nutrient, 0) + amount
        report["nutrient_summary"] = nutrient_totals
    # Summarize sensor readings (24h average per sensor type)
    sensor_data = {}
    for entry in sensor_entries:
        stype = entry.get("sensor_type")
        val = entry.get("value")
        if stype is None or val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue
        sensor_data.setdefault(stype, []).append(val)
    sensor_avg = {stype: round(mean(vals), 2) for stype, vals in sensor_data.items() if vals}
    report["sensor_summary"] = sensor_avg
    # Compare environment readings vs target thresholds using helper
    latest_env = general.get("latest_env", {})
    current_env = {**latest_env, **sensor_avg}
    env_compare = compare_environment(current_env, thresholds)
    report["environment_comparison"] = env_compare
    # Pest and disease alerts (if any observed in profile)
    pest_actions = {}
    disease_actions = {}
    observed_pests = general.get("observed_pests", [])
    observed_diseases = general.get("observed_diseases", [])
    # Load pest treatment guidelines from the bundled dataset
    pest_guidelines = load_dataset("pest_guidelines.json")
    plant_type = general.get("plant_type", "").lower()
    for pest in observed_pests:
        pest_key = str(pest).lower()
        action = None
        if plant_type and plant_type in pest_guidelines and pest_key in pest_guidelines[plant_type]:
            action = pest_guidelines[plant_type][pest_key]
        elif pest_key in pest_guidelines:
            action = pest_guidelines[pest_key]
        if action is None:
            action = f"No guideline available for {pest}."
        pest_actions[pest] = action
    # Basic disease guidelines for common issues (fallback if not in pest_guidelines)
    disease_guidelines = {
        "root rot": "Ensure good drainage and avoid overwatering.",
        "powdery mildew": "Apply appropriate fungicide and remove affected leaves.",
        "blight": "Apply copper-based fungicide at first sign of disease."
    }
    for disease in observed_diseases:
        disease_key = str(disease).lower()
        action = None
        if plant_type and plant_type in pest_guidelines and disease_key in pest_guidelines[plant_type]:
            action = pest_guidelines[plant_type][disease_key]
        if action is None:
            action = disease_guidelines.get(disease_key, f"No guideline available for {disease}.")
        disease_actions[disease] = action
    report["pest_actions"] = pest_actions
    report["disease_actions"] = disease_actions
    # Calculate root zone water metrics (TAW, MAD, current moisture)
    root_depth_cm = general.get("max_root_depth_cm")
    if root_depth_cm is None:
        root_depth_cm = 30.0  # default max root depth (cm)
    try:
        root_depth_cm = float(root_depth_cm)
    except Exception:
        root_depth_cm = 30.0
    # Use default field capacity (20%) and MAD fraction (50%)
    field_capacity = 0.20
    mad_fraction = 0.5
    soil_area_cm2 = 30.0 * 30.0  # assume 30x30 cm surface area
    root_volume_cm3 = root_depth_cm * soil_area_cm2
    total_water_ml = root_volume_cm3 * field_capacity
    readily_avail_ml = total_water_ml * mad_fraction
    root_zone_info = {
        "taw_ml": round(total_water_ml, 1),
        "mad_pct": mad_fraction
    }
    # Include current moisture percentage if a sensor provides it
    moisture_value = None
    for key in ["soil_moisture", "soil_moisture_pct", "moisture"]:
        if key in sensor_avg:
            moisture_value = sensor_avg[key]
            break
    if moisture_value is not None:
        root_zone_info["current_moisture_pct"] = moisture_value
    report["root_zone"] = root_zone_info
    # Include stage details if available in profile
    if stage_name:
        stages = profile.get("stages", {})
        # Check for exact or lowercase match in stage definitions
        stage_key = stage_name if stage_name in stages else stage_name.lower()
        if stage_key in stages and isinstance(stages[stage_key], dict):
            report["stage_info"] = stages[stage_key]
    # Include latest yield measurement (if any in last 24h)
    if yield_entries:
        last_yield = yield_entries[-1].get("yield_quantity")
        report["yield"] = last_yield
    # Save the report to a JSON file with today's date
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{plant_id}_{datetime.utcnow().date()}.json"
    try:
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        _LOGGER.info("Saved daily report for %s to %s", plant_id, out_file)
    except Exception as e:
        _LOGGER.error("Failed to write report for %s: %s", plant_id, e)
    return report