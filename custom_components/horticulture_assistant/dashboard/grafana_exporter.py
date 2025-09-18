import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..utils.json_io import load_json, save_json

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017

_LOGGER = logging.getLogger(__name__)


def export_grafana_data(plant_id: str, base_path: str = "plants", output_path: str = "dashboard") -> dict:
    """
    Compile plant data into a JSON object for Grafana dashboards and write to file.
    Loads the plant profile and the last 7 days of logs, then produces a summary of
    current thresholds, latest sensor readings, and recent soil moisture, EC, irrigation,
    and nutrient data. The result is saved as a JSON file under the output_path.
    """
    base_dir = Path(base_path)
    profile_path = base_dir / f"{plant_id}.json"
    plant_dir = base_dir / plant_id

    data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "threshold_summary": {},
        "sensor_summary": {},
        "irrigation_summary": {},
        "nutrient_summary": {},
    }

    # Load plant profile JSON
    profile = {}
    try:
        profile = load_json(str(profile_path)) or {}
    except FileNotFoundError:
        _LOGGER.error("Plant profile not found: %s", profile_path)
    except Exception as e:
        _LOGGER.error("Failed to load plant profile %s: %s", profile_path, e)

    # Extract current threshold values
    thresholds = {}
    if isinstance(profile.get("thresholds"), dict):
        thresholds = profile["thresholds"]
    elif isinstance(profile.get("profile_data"), dict) and isinstance(profile["profile_data"].get("thresholds"), dict):
        thresholds = profile["profile_data"]["thresholds"]
    data["threshold_summary"] = thresholds

    # Extract latest sensor values from profile (general.latest_env if present)
    latest_env = {}
    if isinstance(profile.get("general"), dict):
        latest_env = profile["general"].get("latest_env", {})
    elif "latest_env" in profile:
        latest_env = profile.get("latest_env", {})
    if isinstance(latest_env, dict):
        data["sensor_summary"].update(latest_env)

    # Helper to load JSON log files safely
    def _load_log(path: Path):
        try:
            return load_json(str(path)) or []
        except FileNotFoundError:
            _LOGGER.info("Log file not found: %s", path)
            return []
        except Exception as e:
            _LOGGER.warning("Error reading log file %s: %s", path, e)
            return []

    # Calculate cutoff for last 7 days
    now = datetime.now(UTC)
    cutoff_time = now - timedelta(days=7)

    def _filter_last_7d(entries):
        recent = []
        for entry in entries:
            ts = entry.get("timestamp")
            if not ts:
                continue
            try:
                t = datetime.fromisoformat(ts)
            except Exception:
                # Skip entries with unparseable timestamps
                continue
            if t >= cutoff_time:
                recent.append(entry)
        return recent

    # Load and filter log data for the last 7 days
    irrigation_entries = _filter_last_7d(_load_log(plant_dir / "irrigation_log.json"))
    nutrient_entries = _filter_last_7d(_load_log(plant_dir / "nutrient_application_log.json"))
    sensor_entries = _filter_last_7d(_load_log(plant_dir / "sensor_reading_log.json"))

    # Summarize last 7 days of irrigation events
    if irrigation_entries:
        total_volume = sum(entry.get("volume_applied_ml", 0) or 0 for entry in irrigation_entries)
        methods = {entry.get("method") for entry in irrigation_entries if entry.get("method")}
        irrigation_summary = {
            "events": len(irrigation_entries),
            "total_volume_ml": total_volume,
        }
        if methods:
            irrigation_summary["methods"] = list(methods)
        data["irrigation_summary"] = irrigation_summary

    # Summarize last 7 days of nutrient applications
    if nutrient_entries:
        nutrient_totals = {}
        for entry in nutrient_entries:
            formulation = entry.get("nutrient_formulation", {})
            if isinstance(formulation, dict):
                for nutrient, amount in formulation.items():
                    # Sum amounts (skip non-numeric values)
                    try:
                        amt = float(amount)
                    except Exception:
                        continue
                    nutrient_totals[nutrient] = nutrient_totals.get(nutrient, 0.0) + amt
        data["nutrient_summary"] = nutrient_totals

    # Summarize last 7 days of sensor readings (focus on soil moisture and EC)
    if sensor_entries:
        sensor_vals = {}
        for entry in sensor_entries:
            stype = entry.get("sensor_type")
            val = entry.get("value")
            if stype is None or val is None:
                continue
            try:
                num_val = float(val)
            except Exception:
                # skip non-numeric sensor readings
                continue
            sensor_vals.setdefault(stype, []).append(num_val)
        for stype, values in sensor_vals.items():
            if not values:
                continue
            avg_val = round(sum(values) / len(values), 2)
            # Only include key metrics (soil moisture, EC) as 7-day averages
            stype_lower = str(stype).lower()
            if "moisture" in stype_lower or stype_lower == "ec":
                data["sensor_summary"][f"{stype}_avg_7d"] = avg_val

    # Ensure the output directory exists
    output_dir = Path(output_path)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Could not create output directory %s: %s", output_dir, e)

    # Write the resulting data to a JSON file
    output_file = output_dir / f"{plant_id}_grafana.json"
    try:
        save_json(str(output_file), data)
        _LOGGER.info("Grafana export saved for plant %s at %s", plant_id, output_file)
    except Exception as e:
        _LOGGER.error("Failed to write Grafana export for plant %s: %s", plant_id, e)

    return data
