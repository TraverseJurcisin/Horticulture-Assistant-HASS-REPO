"""Daily report generation for plant profiles.

This module summarizes irrigation, nutrient applications and sensor readings
from the previous 24 hours into a structured report suitable for automations
or dashboards.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean

from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    load_profile_by_id,
)
from plant_engine.environment_manager import compare_environment, optimize_environment
from plant_engine.growth_stage import predict_harvest_date
from plant_engine.pest_manager import recommend_beneficials
from plant_engine.pest_monitor import classify_pest_severity
from plant_engine.utils import load_dataset
from plant_engine.fertigation import recommend_nutrient_mix
from plant_engine.nutrient_analysis import analyze_nutrient_profile
from plant_engine.rootzone_model import estimate_water_capacity


@dataclass
class DailyReport:
    """Structured daily report data."""

    plant_id: str
    lifecycle_stage: str = "unknown"
    thresholds: dict[str, object] = field(default_factory=dict)
    irrigation_summary: dict[str, object] = field(default_factory=dict)
    nutrient_summary: dict[str, object] = field(default_factory=dict)
    nutrient_analysis: dict[str, object] = field(default_factory=dict)
    sensor_summary: dict[str, object] = field(default_factory=dict)
    environment_comparison: dict[str, object] = field(default_factory=dict)
    environment_optimization: dict[str, object] = field(default_factory=dict)
    pest_actions: dict[str, str] = field(default_factory=dict)
    disease_actions: dict[str, str] = field(default_factory=dict)
    beneficial_insects: dict[str, list[str]] = field(default_factory=dict)
    pest_severity: dict[str, str] = field(default_factory=dict)
    root_zone: dict[str, object] = field(default_factory=dict)
    stage_info: dict[str, object] = field(default_factory=dict)
    fertigation_schedule: dict[str, float] = field(default_factory=dict)
    irrigation_target_ml: float | None = None
    predicted_harvest_date: str | None = None
    yield_: float | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def as_dict(self) -> dict:
        return asdict(self)

_LOGGER = logging.getLogger(__name__)


def _load_recent_entries(log_path: Path, hours: float = 24.0) -> list[dict]:
    """Return log entries from ``log_path`` within the last ``hours``."""

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _LOGGER.info("Log file not found: %s", log_path)
        return []
    except Exception as exc:  # noqa: broad-except -- log any failure
        _LOGGER.warning("Failed to read %s: %s", log_path, exc)
        return []

    cutoff = datetime.utcnow() - timedelta(hours=hours)
    recent: list[dict] = []
    for entry in data:
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts) >= cutoff:
                recent.append(entry)
        except Exception:  # noqa: broad-except -- skip malformed entry
            continue

    return recent

def run_daily_cycle(
    plant_id: str, base_path: str = "plants", output_path: str = "data/daily_reports"
) -> dict:
    """Return an aggregated 24h report for ``plant_id``.

    The report includes irrigation, nutrients, sensor averages, environment
    analysis and optional fertigation recommendations.
    """

    plant_dir = Path(base_path) / plant_id
    report = DailyReport(plant_id)
    # Load plant profile (structured data)
    profile = load_profile_by_id(plant_id, base_dir=base_path)
    if not profile:
        _LOGGER.error("No profile found for plant_id %s", plant_id)
        return report
    # Determine current lifecycle stage
    general = profile.get("general", {})
    stage_name = general.get("lifecycle_stage") or general.get("stage")
    plant_type = general.get("plant_type", "").lower()
    if stage_name:
        report.lifecycle_stage = stage_name
    # Get current thresholds from profile
    thresholds = profile.get("thresholds", {})
    report.thresholds = thresholds
    # Load last 24h logs for irrigation, nutrients, sensors, visuals, yield
    irrigation_entries = _load_recent_entries(plant_dir / "irrigation_log.json")
    nutrient_entries = _load_recent_entries(plant_dir / "nutrient_application_log.json")
    sensor_entries = _load_recent_entries(plant_dir / "sensor_reading_log.json")
    yield_entries = _load_recent_entries(plant_dir / "yield_tracking_log.json")
    # Summarize irrigation events (24h)
    if irrigation_entries:
        total_volume = sum(e.get("volume_applied_ml", 0) for e in irrigation_entries)
        methods = {e.get("method") for e in irrigation_entries if e.get("method")}
        report.irrigation_summary = {
            "events": len(irrigation_entries),
            "total_volume_ml": total_volume,
            "methods": list(methods)
        }
    # Summarize nutrient applications (aggregate nutrients applied in 24h)
    if nutrient_entries:
        nutrient_totals: dict[str, float] = {}
        for entry in nutrient_entries:
            formulation = entry.get("nutrient_formulation", {})
            for nutrient, amount in formulation.items():
                nutrient_totals[nutrient] = nutrient_totals.get(nutrient, 0) + amount
        report.nutrient_summary = nutrient_totals
        try:
            report.nutrient_analysis = analyze_nutrient_profile(
                nutrient_totals, plant_type, stage_name or ""
            )
        except Exception:
            _LOGGER.debug("Failed to analyze nutrient profile", exc_info=True)
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
    report.sensor_summary = sensor_avg
    # Compare environment readings vs target thresholds using helper
    latest_env = general.get("latest_env", {})
    current_env = {**latest_env, **sensor_avg}
    env_compare = compare_environment(current_env, thresholds)
    report.environment_comparison = env_compare
    report.environment_optimization = optimize_environment(
        current_env, plant_type, stage_name
    )
    # Pest and disease alerts (if any observed in profile)
    pest_actions = {}
    disease_actions = {}
    observed_pests = general.get("observed_pests", [])
    observed_diseases = general.get("observed_diseases", [])
    # Load pest treatment guidelines from the bundled dataset
    pest_guidelines = load_dataset("pest_guidelines.json")
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
    report.pest_actions = pest_actions
    report.disease_actions = disease_actions
    # Suggest beneficial insects for observed pests
    if observed_pests:
        report.beneficial_insects = recommend_beneficials(observed_pests)

    observed_counts = general.get("observed_pest_counts")
    if isinstance(observed_counts, dict):
        try:
            report.pest_severity = classify_pest_severity(plant_type, observed_counts)
        except Exception:
            _LOGGER.debug("Failed to classify pest severity", exc_info=True)

    # Predict harvest date if a start date is provided
    start_date_str = general.get("start_date")
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str).date()
            harvest = predict_harvest_date(general.get("plant_type", ""), start_date)
            if harvest:
                report.predicted_harvest_date = harvest.isoformat()
        except Exception:  # noqa: broad-except -- ignore parse errors
            pass
    # Calculate root zone water metrics (TAW, MAD, current moisture)
    root_depth_cm = general.get("max_root_depth_cm", 30.0)
    try:
        root_depth_cm = float(root_depth_cm)
    except Exception:
        root_depth_cm = 30.0

    rootzone = estimate_water_capacity(root_depth_cm)
    root_zone_info = {
        "taw_ml": rootzone.total_available_water_ml,
        "mad_pct": rootzone.mad_pct,
    }
    # Include current moisture percentage if a sensor provides it
    moisture_value = None
    for key in ["soil_moisture", "soil_moisture_pct", "moisture"]:
        if key in sensor_avg:
            moisture_value = sensor_avg[key]
            break
    if moisture_value is not None:
        root_zone_info["current_moisture_pct"] = moisture_value
    report.root_zone = root_zone_info

    # Irrigation and fertigation targets
    irrigation_data = load_dataset("irrigation_guidelines.json")
    report.irrigation_target_ml = (
        irrigation_data.get(plant_type, {}).get(stage_name or "")
    )
    if report.irrigation_target_ml:
        vol_l = report.irrigation_target_ml / 1000
        report.fertigation_schedule = recommend_nutrient_mix(
            plant_type,
            stage_name or "",
            vol_l,
            include_micro=True,
        )
    # Include stage details if available in profile
    if stage_name:
        stages = profile.get("stages", {})
        # Check for exact or lowercase match in stage definitions
        stage_key = stage_name if stage_name in stages else stage_name.lower()
        if stage_key in stages and isinstance(stages[stage_key], dict):
            report.stage_info = stages[stage_key]
    # Include latest yield measurement (if any in last 24h)
    if yield_entries:
        last_yield = yield_entries[-1].get("yield_quantity")
        report.yield_ = last_yield
    # Save the report to a JSON file with today's date
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{plant_id}_{datetime.utcnow().date()}.json"
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report.as_dict(), f, indent=2)
        _LOGGER.info("Saved daily report for %s to %s", plant_id, out_file)
    except Exception as e:
        _LOGGER.error("Failed to write report for %s: %s", plant_id, e)
    return report.as_dict()
