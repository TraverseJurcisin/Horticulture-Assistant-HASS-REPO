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
from typing import Mapping

from custom_components.horticulture_assistant.utils.path_utils import (
    plants_path,
    data_path,
)

from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    load_profile_by_id,
)
from plant_engine.environment_manager import (
    compare_environment,
    optimize_environment,
    score_environment,
    classify_environment_quality,
)
from plant_engine.growth_stage import predict_harvest_date, stage_progress
from plant_engine.pest_manager import recommend_beneficials, recommend_treatments
from plant_engine.disease_manager import (
    recommend_treatments as recommend_disease_treatments,
)
from plant_engine.deficiency_manager import diagnose_deficiency_actions
from plant_engine.pest_monitor import classify_pest_severity
import plant_engine.pest_monitor as pest_monitor
from plant_engine.utils import load_dataset
from .cycle_helpers import (
    load_recent_entries as _load_recent_entries,
    load_last_entry,
    summarize_irrigation as _summarize_irrigation,
    aggregate_nutrients as _aggregate_nutrients,
    average_sensor_data as _average_sensor_data,
    compute_expected_uptake as _compute_expected_uptake,
    load_logs as _load_logs,
    build_root_zone_info as _build_root_zone_info,
)
from plant_engine.fertigation import (
    recommend_nutrient_mix,
    recommend_nutrient_mix_with_cost,
)
from plant_engine.nutrient_analysis import analyze_nutrient_profile
from plant_engine.compute_transpiration import compute_transpiration
from plant_engine.rootzone_model import estimate_infiltration_time
from plant_engine.yield_prediction import estimate_remaining_yield
from plant_engine.stage_tasks import get_stage_tasks
from custom_components.horticulture_assistant.utils.stage_nutrient_requirements import (
    calculate_stage_deficit,
)
from plant_engine import water_quality


@dataclass(slots=True)
class DailyReport:
    """Structured daily report data."""

    plant_id: str
    lifecycle_stage: str = "unknown"
    thresholds: dict[str, object] = field(default_factory=dict)
    irrigation_summary: dict[str, object] = field(default_factory=dict)
    nutrient_summary: dict[str, object] = field(default_factory=dict)
    expected_uptake: dict[str, float] = field(default_factory=dict)
    uptake_gap: dict[str, float] = field(default_factory=dict)
    stage_deficit: dict[str, float] = field(default_factory=dict)
    nutrient_analysis: dict[str, object] = field(default_factory=dict)
    sensor_summary: dict[str, object] = field(default_factory=dict)
    environment_comparison: dict[str, object] = field(default_factory=dict)
    environment_optimization: dict[str, object] = field(default_factory=dict)
    environment_score: float | None = None
    environment_quality: str | None = None
    pest_actions: dict[str, str] = field(default_factory=dict)
    disease_actions: dict[str, str] = field(default_factory=dict)
    deficiency_actions: dict[str, dict[str, str]] = field(default_factory=dict)
    beneficial_insects: dict[str, list[str]] = field(default_factory=dict)
    pest_severity: dict[str, str] = field(default_factory=dict)
    next_pest_monitor_date: str | None = None
    root_zone: dict[str, object] = field(default_factory=dict)
    transpiration: dict[str, float] = field(default_factory=dict)
    water_quality_summary: dict[str, object] = field(default_factory=dict)
    stage_info: dict[str, object] = field(default_factory=dict)
    stage_tasks: list[str] = field(default_factory=list)
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


def run_daily_cycle(
    plant_id: str,
    base_path: str | None = None,
    output_path: str | None = None,
) -> dict:
    """Return an aggregated 24h report for ``plant_id``.

    The report summarizes irrigation, nutrient applications, sensor data and
    environmental conditions from the previous day.  Results are saved to a
    dated JSON file for use by automations or dashboards.

    ``base_path`` and ``output_path`` default to the configured ``plants`` and
    ``data/daily_reports`` directories, respectively.
    """

    if base_path is None:
        base_path = plants_path(None)
    if output_path is None:
        output_path = data_path(None, "daily_reports")

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
    logs = _load_logs(plant_dir)
    irrigation_entries = logs["irrigation"]
    nutrient_entries = logs["nutrient"]
    sensor_entries = logs["sensor"]
    water_quality_entries = logs["water_quality"]
    yield_entries = logs["yield"]

    report.irrigation_summary = _summarize_irrigation(irrigation_entries)

    nutrient_totals = _aggregate_nutrients(nutrient_entries)
    report.nutrient_summary = nutrient_totals

    try:
        report.nutrient_analysis = analyze_nutrient_profile(
            nutrient_totals, plant_type, stage_name or ""
        ).as_dict()
        report.deficiency_actions = diagnose_deficiency_actions(
            nutrient_totals, plant_type, stage_name or ""
        )
    except Exception:  # noqa: BLE001 -- analysis failure shouldn't halt cycle
        _LOGGER.debug("Failed to analyze nutrient profile", exc_info=True)

    expected, gap = _compute_expected_uptake(
        plant_type, stage_name or "", nutrient_totals
    )
    report.expected_uptake = expected
    report.uptake_gap = gap
    report.stage_deficit = calculate_stage_deficit(
        nutrient_totals, plant_type, stage_name or ""
    )

    # Summarize sensor readings (24h average per sensor type)
    sensor_avg = _average_sensor_data(sensor_entries)
    report.sensor_summary = sensor_avg

    # Include water quality analysis using the most recent test
    if water_quality_entries:
        latest = water_quality_entries[-1]
        test = latest.get("results", latest)
        if isinstance(test, dict):
            report.water_quality_summary = water_quality.summarize_water_profile(test).as_dict()
    # Compare environment readings vs target thresholds using helper
    latest_env = general.get("latest_env", {})
    current_env = {**latest_env, **sensor_avg}
    env_compare = compare_environment(current_env, thresholds)
    report.environment_comparison = env_compare
    report.environment_optimization = optimize_environment(
        current_env, plant_type, stage_name
    )
    report.environment_score = score_environment(current_env, plant_type, stage_name)
    report.environment_quality = classify_environment_quality(
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

    # Determine next recommended pest scouting date
    last_scout = load_last_entry(plant_dir / "pest_scouting_log.json")
    if last_scout and "timestamp" in last_scout:
        try:
            last_date = datetime.fromisoformat(last_scout["timestamp"]).date()
            interval = pest_monitor.risk_adjusted_monitor_interval(
                plant_type, stage_name, current_env
            )
            if interval is not None:
                next_date = last_date + timedelta(days=interval)
            else:
                next_date = pest_monitor.next_monitor_date(
                    plant_type, stage_name, last_date
                )
            if next_date:
                report.next_pest_monitor_date = next_date.isoformat()
        except Exception:  # noqa: BLE001 -- optional
            _LOGGER.debug("Failed to parse pest scouting log", exc_info=True)

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
    root_zone_info = _build_root_zone_info(general, sensor_avg)
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
        # Estimate how long the irrigation volume takes to infiltrate
        soil_texture = general.get("soil_texture", "loam")
        area_m2 = float(general.get("surface_area_m2", 0.09))
        infil = estimate_infiltration_time(report.irrigation_target_ml, area_m2, soil_texture)
        if infil is not None:
            report.root_zone["infiltration_time_hr"] = infil
    # Include stage details and progress if available in profile
    if stage_name:
        stages = profile.get("stages", {})
        stage_key = stage_name if stage_name in stages else stage_name.lower()
        if stage_key in stages and isinstance(stages[stage_key], dict):
            report.stage_info = stages[stage_key]
        tasks = get_stage_tasks(plant_type, stage_name)
        if tasks:
            report.stage_tasks = tasks
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


__all__ = [
    "DailyReport",
    "run_daily_cycle",
    "_aggregate_nutrients",
    "_average_sensor_data",
    "_build_root_zone_info",
    "_compute_expected_uptake",
    "_load_logs",
    "_load_recent_entries",
    "_summarize_irrigation",
    "load_last_entry",
]
