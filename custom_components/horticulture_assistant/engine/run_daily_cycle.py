"""Daily report generation for plant profiles.

This module summarizes irrigation, nutrient applications and sensor readings
from the previous 24 hours into a structured report suitable for automations
or dashboards.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    load_profile_by_id,
)
from plant_engine.environment_manager import compare_environment, optimize_environment
from plant_engine.growth_stage import predict_harvest_date, stage_progress
from plant_engine.pest_manager import recommend_beneficials, recommend_treatments
from plant_engine.disease_manager import (
    recommend_treatments as recommend_disease_treatments,
)
from plant_engine.deficiency_manager import diagnose_deficiency_actions
from plant_engine.pest_monitor import classify_pest_severity
from plant_engine.utils import load_dataset
from plant_engine.fertigation import (
    recommend_nutrient_mix,
    recommend_nutrient_mix_with_cost,
)
from plant_engine.nutrient_analysis import analyze_nutrient_profile
from plant_engine.compute_transpiration import compute_transpiration
from plant_engine.rootzone_model import estimate_water_capacity
from plant_engine.yield_prediction import estimate_remaining_yield


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
    deficiency_actions: dict[str, dict[str, str]] = field(default_factory=dict)
    beneficial_insects: dict[str, list[str]] = field(default_factory=dict)
    pest_severity: dict[str, str] = field(default_factory=dict)
    root_zone: dict[str, object] = field(default_factory=dict)
    transpiration: dict[str, float] = field(default_factory=dict)
    stage_info: dict[str, object] = field(default_factory=dict)
    stage_progress_pct: float | None = None
    fertigation_schedule: dict[str, float] = field(default_factory=dict)
    fertigation_cost: float | None = None
    irrigation_target_ml: float | None = None
    predicted_harvest_date: str | None = None
    yield_: float | None = None
    remaining_yield_g: float | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def as_dict(self) -> dict:
        return asdict(self)


_LOGGER = logging.getLogger(__name__)


def _load_recent_entries(log_path: Path, hours: float = 24.0) -> list[dict]:
    """Return log entries from ``log_path`` within the last ``hours``."""

    try:
        with log_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _LOGGER.info("Log file not found: %s", log_path)
        return []
    except Exception as exc:  # noqa: BLE001 -- log any failure
        _LOGGER.warning("Failed to read %s: %s", log_path, exc)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    def in_range(entry: dict) -> bool:
        ts = entry.get("timestamp")
        if not ts:
            return False
        try:
            return datetime.fromisoformat(ts) >= cutoff
        except Exception:
            return False

    return [e for e in data if in_range(e)]


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
            "methods": list(methods),
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
                nutrient_totals,
                plant_type,
                stage_name or "",
            )
            report.deficiency_actions = diagnose_deficiency_actions(
                nutrient_totals,
                plant_type,
                stage_name or "",
            )
        except Exception:  # noqa: BLE001 -- analysis failure shouldn't halt cycle
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
    sensor_avg = {
        stype: round(mean(vals), 2) for stype, vals in sensor_data.items() if vals
    }
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
    observed_pests = general.get("observed_pests", [])
    observed_diseases = general.get("observed_diseases", [])

    pest_actions = recommend_treatments(plant_type, observed_pests)
    disease_actions = recommend_disease_treatments(plant_type, observed_diseases)

    report.pest_actions = pest_actions
    report.disease_actions = disease_actions
    # Suggest beneficial insects for observed pests
    if observed_pests:
        report.beneficial_insects = recommend_beneficials(observed_pests)

    observed_counts = general.get("observed_pest_counts")
    if isinstance(observed_counts, dict):
        try:
            report.pest_severity = classify_pest_severity(plant_type, observed_counts)
        except Exception:  # noqa: BLE001 -- classification failure not critical
            _LOGGER.debug("Failed to classify pest severity", exc_info=True)

    # Predict harvest date if a start date is provided
    start_date_str = general.get("start_date")
    if start_date_str:
        try:
            start_date = datetime.fromisoformat(start_date_str).date()
            harvest = predict_harvest_date(general.get("plant_type", ""), start_date)
            if harvest:
                report.predicted_harvest_date = harvest.isoformat()
        except Exception:  # noqa: BLE001 -- ignore parse errors
            pass
    # Calculate root zone water metrics (TAW, MAD, current moisture)
    root_depth_cm = general.get("max_root_depth_cm", 30.0)
    try:
        root_depth_cm = float(root_depth_cm)
    except Exception:  # noqa: BLE001 -- default on parse failure
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

    # Estimate plant transpiration based on latest environment readings
    canopy_m2 = general.get("canopy_m2", 0.25)
    try:
        canopy_m2 = float(canopy_m2)
    except Exception:
        canopy_m2 = 0.25
    plant_info = {"plant_type": plant_type, "stage": stage_name, "canopy_m2": canopy_m2}
    report.transpiration = compute_transpiration(plant_info, current_env)

    # Irrigation and fertigation targets
    irrigation_data = load_dataset("irrigation_guidelines.json")
    report.irrigation_target_ml = irrigation_data.get(plant_type, {}).get(
        stage_name or ""
    )
    if report.irrigation_target_ml:
        vol_l = report.irrigation_target_ml / 1000
        try:
            schedule, cost = recommend_nutrient_mix_with_cost(
                plant_type,
                stage_name or "",
                vol_l,
                include_micro=True,
            )
        except KeyError:
            schedule = recommend_nutrient_mix(
                plant_type,
                stage_name or "",
                vol_l,
                include_micro=True,
            )
            cost = None
        report.fertigation_schedule = schedule
        report.fertigation_cost = cost
    # Include stage details and progress if available in profile
    if stage_name:
        stages = profile.get("stages", {})
        stage_key = stage_name if stage_name in stages else stage_name.lower()
        if stage_key in stages and isinstance(stages[stage_key], dict):
            report.stage_info = stages[stage_key]
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str).date()
                days = (datetime.now(timezone.utc).date() - start_date).days
                progress = stage_progress(plant_type, stage_name, days)
                if progress is not None:
                    report.stage_progress_pct = progress
            except Exception:  # noqa: BLE001 -- optional
                pass
    # Include latest yield measurement (if any in last 24h)
    if yield_entries:
        last_yield = yield_entries[-1].get("yield_quantity")
        report.yield_ = last_yield
    # Estimate remaining yield from logged harvests and expectations
    remaining = estimate_remaining_yield(plant_id, plant_type)
    if remaining is not None:
        report.remaining_yield_g = remaining
    # Save the report to a JSON file with today's date
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{plant_id}_{datetime.now(timezone.utc).date()}.json"
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report.as_dict(), f, indent=2)
        _LOGGER.info("Saved daily report for %s to %s", plant_id, out_file)
    except Exception as e:  # noqa: BLE001 -- log write failures
        _LOGGER.error("Failed to write report for %s: %s", plant_id, e)
    return report.as_dict()
