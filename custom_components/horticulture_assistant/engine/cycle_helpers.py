"""Reusable helpers for daily cycle processing."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean

from plant_engine.nutrient_uptake import get_daily_uptake
from plant_engine.rootzone_model import estimate_water_capacity

# Default depth used when profiles omit ``max_root_depth_cm``.
DEFAULT_ROOT_DEPTH_CM = 30.0

__all__ = [
    "aggregate_nutrients",
    "average_sensor_data",
    "build_root_zone_info",
    "compute_expected_uptake",
    "load_last_entry",
    "load_logs",
    "load_recent_entries",
    "summarize_irrigation",
]


def load_recent_entries(log_path: Path, hours: float = 24.0) -> list[dict]:
    """Return log entries from ``log_path`` within the last ``hours``.

    Missing files yield an empty list and malformed JSON is ignored.
    """
    try:
        with log_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    result: list[dict] = []
    for entry in data:
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            continue
        if dt >= cutoff:
            result.append(entry)
    return result


def load_last_entry(log_path: Path) -> dict | None:
    """Return the most recent entry from ``log_path``."""
    try:
        with log_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except Exception:
        return None
    if isinstance(data, list) and data:
        return data[-1]
    return None


def summarize_irrigation(entries: list[dict]) -> dict[str, object]:
    """Return irrigation summary statistics for ``entries``."""
    if not entries:
        return {}
    total_volume = sum(e.get("volume_applied_ml", 0) for e in entries)
    methods = {e.get("method") for e in entries if e.get("method")}
    return {
        "events": len(entries),
        "total_volume_ml": total_volume,
        "methods": list(methods),
    }


def aggregate_nutrients(entries: list[dict]) -> dict[str, float]:
    """Return total nutrient amounts from ``entries``."""
    totals: dict[str, float] = {}
    for entry in entries:
        formulation = entry.get("nutrient_formulation", {})
        for nutrient, amount in formulation.items():
            totals[nutrient] = totals.get(nutrient, 0.0) + amount
    return totals


def average_sensor_data(entries: list[dict]) -> dict[str, float]:
    """Return average value for each sensor type in ``entries``."""
    data: dict[str, list[float]] = {}
    for entry in entries:
        stype = entry.get("sensor_type")
        val = entry.get("value")
        if stype is None or val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue
        data.setdefault(stype, []).append(val)
    return {stype: round(mean(vals), 2) for stype, vals in data.items() if vals}


def compute_expected_uptake(
    plant_type: str, stage: str, totals: Mapping[str, float]
) -> tuple[dict[str, float], dict[str, float]]:
    """Return expected daily nutrient uptake and remaining gap."""
    expected = get_daily_uptake(plant_type, stage)
    if not expected:
        return {}, {}
    gap: dict[str, float] = {}
    for nutrient, target in expected.items():
        applied = totals.get(nutrient, 0.0)
        gap[nutrient] = round(target - applied, 2)
    return expected, gap


def load_logs(plant_dir: Path) -> dict[str, list]:
    """Return recent log entries for the given plant directory."""

    return {
        "irrigation": load_recent_entries(plant_dir / "irrigation_log.json"),
        "nutrient": load_recent_entries(plant_dir / "nutrient_application_log.json"),
        "sensor": load_recent_entries(plant_dir / "sensor_reading_log.json"),
        "water_quality": load_recent_entries(plant_dir / "water_quality_log.json"),
        "yield": load_recent_entries(plant_dir / "yield_tracking_log.json"),
    }


def build_root_zone_info(
    general: Mapping[str, object], sensor_avg: Mapping[str, float]
) -> dict[str, object]:
    """Return root zone metrics calculated from profile and sensors."""

    try:
        root_depth_cm = float(general.get("max_root_depth_cm", DEFAULT_ROOT_DEPTH_CM))
    except Exception:
        root_depth_cm = DEFAULT_ROOT_DEPTH_CM

    zone = estimate_water_capacity(root_depth_cm)
    info = {
        "taw_ml": zone.total_available_water_ml,
        "mad_pct": zone.mad_pct,
    }
    for key in ("soil_moisture", "soil_moisture_pct", "moisture"):
        if key in sensor_avg:
            info["current_moisture_pct"] = sensor_avg[key]
            break

    return info
