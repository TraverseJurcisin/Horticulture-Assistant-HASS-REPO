from __future__ import annotations

import json
import logging
import os
from datetime import datetime

# Reuse the central evapotranspiration formulas from plant_engine
from plant_engine.et_model import calculate_et0, calculate_eta

from custom_components.horticulture_assistant.utils.path_utils import data_path, plants_path

try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None

_LOGGER = logging.getLogger(__name__)

# Growth rate modifiers for each lifecycle stage (stage-based multiplier for vegetative growth)
STAGE_GROWTH_MODIFIERS = {"seedling": 0.5, "vegetative": 1.0, "flowering": 0.7, "fruiting": 0.5}

# Ideal environmental conditions (used for expected growth calculations)
IDEAL_ENV_DEFAULT = {
    "temp_c": 26.0,
    "temp_c_max": 30.0,
    "temp_c_min": 22.0,
    "rh_pct": 65.0,
    "par": 350.0,  # approximate PAR (W/m²) for a bright day
    "wind_speed_m_s": 1.2,
    "elevation_m": 200.0,
}


def update_growth_index(
    hass: HomeAssistant | None,
    plant_id: str,
    env_data: dict,
    transpiration_ml: float | None = None,
) -> dict:
    """
    Update the daily vegetative growth index (VGI) for a given plant.

    Uses daily light (DLI or PAR), temperature (growing degree days), and profile stage-based modifiers
    to calculate today's VGI. Accumulates VGI over time and compares against expected growth for the
    current lifecycle stage based on stage duration and ideal conditions.

    Saves the growth trend as a time series (JSON) in data/growth_trends.json and returns a summary dict.
    """
    # Load plant profile to get current stage and any relevant parameters
    profile = {}
    try:
        from custom_components.horticulture_assistant.utils.bio_profile_loader import load_profile

        base_dir = plants_path(hass)
        profile = load_profile(plant_id=plant_id, base_dir=base_dir)
    except Exception as e:
        _LOGGER.error("Could not load profile for plant %s: %s", plant_id, e)
        profile = {}
    if not profile:
        _LOGGER.error("Plant profile for '%s' is missing or empty. Cannot update growth index.", plant_id)
        return {}

    # Determine current lifecycle stage
    stage = profile.get("general", {}).get("lifecycle_stage") or profile.get("general", {}).get("stage") or "unknown"
    stage_lower = str(stage).lower()
    # Get stage details (duration, optional growth modifiers)
    stage_data = profile.get("stages", {}).get(stage, {}) or profile.get("stages", {}).get(stage_lower, {})
    stage_duration_days = stage_data.get("stage_duration") if isinstance(stage_data, dict) else None

    # Base temperature for GDD (threshold below which no growth accrues)
    base_temp_c = profile.get("general", {}).get("base_temp_c", 10.0)

    # Calculate Growing Degree Days (GDD) for today
    gdd = 0.0
    if "temp_c_max" in env_data and "temp_c_min" in env_data:
        # Use average of daily max/min temperatures
        gdd = ((env_data["temp_c_max"] + env_data["temp_c_min"]) / 2) - base_temp_c
    elif "temperature" in env_data or "temp_c" in env_data:
        # Fallback to a single temperature reading (e.g., average or current temp)
        temp_val = env_data.get("temperature", env_data.get("temp_c"))
        if temp_val is not None:
            try:
                temp_val = float(temp_val)
            except (ValueError, TypeError):
                temp_val = None
        if temp_val is not None:
            gdd = temp_val - base_temp_c
    # Only positive GDD contributes to growth
    gdd = max(gdd, 0.0)

    # Determine daily light (PAR in MJ/m² or DLI in mol/m²) for growth
    par_mj = 0.0
    dli_mol = None
    if "dli" in env_data or "dli_mol_m2" in env_data or "dli_mol" in env_data:
        # Use provided Daily Light Integral (mol/m²/day)
        dli_val = env_data.get("dli") or env_data.get("dli_mol_m2") or env_data.get("dli_mol")
        try:
            dli_val = float(dli_val)
        except (ValueError, TypeError):
            dli_val = None
        if dli_val is not None:
            dli_mol = dli_val
            # Convert DLI to PAR energy (approx 0.218 MJ per mole of photons)
            par_mj = dli_val * 0.218
    if dli_mol is None:
        # If DLI not provided, use PAR or generic light reading
        par_val = env_data.get("par_w_m2") or env_data.get("par")
        if par_val is None:
            # Approximate PAR (W/m²) from a brightness sensor (lux) if available
            light_val = env_data.get("light")
            if light_val is not None:
                try:
                    light_val = float(light_val)
                except (ValueError, TypeError):
                    light_val = None
            if light_val is not None:
                # Rough conversion: ~1 W/m² per 120 lux for sunlight spectrum
                par_val = light_val / 120.0
                _LOGGER.debug(
                    "Approximating PAR from lux for %s: %s lux -> %.2f W/m²",
                    plant_id,
                    light_val,
                    par_val,
                )
        if par_val is not None:
            try:
                par_val = float(par_val)
            except (ValueError, TypeError):
                par_val = None
        if par_val is not None:
            # Convert average W/m² to MJ/m²/day
            par_mj = par_val * 0.0864
            # Estimate DLI (mol/day) from PAR energy
            dli_mol = par_mj / 0.218
        else:
            # No light data available for this day
            par_mj = 0.0
            dli_mol = 0.0
            _LOGGER.warning("No light/DLI data for plant %s; setting growth index to 0 for today.", plant_id)

    # Determine transpiration factor (daily water use) in liters
    if transpiration_ml is not None:
        # Use provided transpiration (ml/day) if given
        try:
            transpiration_ml = float(transpiration_ml)
        except (ValueError, TypeError):
            transpiration_ml = 0.0
        et_liters = transpiration_ml / 1000.0
    else:
        # Calculate ET-based transpiration if not provided
        temp_for_et = env_data.get("temp_c") or env_data.get("temperature")
        rh_for_et = env_data.get("rh_pct") or env_data.get("humidity")
        solar_for_et = env_data.get("par") or env_data.get("par_w_m2")
        if solar_for_et is None and env_data.get("light") is not None:
            # Use light reading to approximate solar radiation if needed
            try:
                solar_for_et = float(env_data.get("light")) / 120.0  # lux to W/m²
            except (ValueError, TypeError):
                solar_for_et = None
        wind_for_et = env_data.get("wind_speed_m_s", IDEAL_ENV_DEFAULT["wind_speed_m_s"])
        elev_for_et = env_data.get("elevation_m", IDEAL_ENV_DEFAULT["elevation_m"])
        # Fallback to default ideal env values if any key data is missing
        if temp_for_et is None:
            temp_for_et = IDEAL_ENV_DEFAULT["temp_c"]
        if rh_for_et is None:
            rh_for_et = IDEAL_ENV_DEFAULT["rh_pct"]
        if solar_for_et is None:
            solar_for_et = IDEAL_ENV_DEFAULT["par"]
        try:
            temp_for_et = float(temp_for_et)
            rh_for_et = float(rh_for_et)
            solar_for_et = float(solar_for_et)
            wind_for_et = float(wind_for_et)
            elev_for_et = float(elev_for_et)
        except Exception as err:
            _LOGGER.debug("Error parsing env data for ET calculation (%s). Using defaults.", err)
        # Crop coefficient (Kc) and canopy area from profile (with defaults)
        kc = profile.get("general", {}).get("kc", profile.get("kc", 1.0))
        canopy_m2 = profile.get("general", {}).get("canopy_m2", profile.get("canopy_m2", 0.25))
        try:
            kc = float(kc)
        except (ValueError, TypeError):
            kc = 1.0
        try:
            canopy_m2 = float(canopy_m2)
        except (ValueError, TypeError):
            canopy_m2 = 0.25
        # Compute ET₀ and ETₐ (mm/day)
        et0_mm = calculate_et0(temp_for_et, rh_for_et, solar_for_et, wind_m_s=wind_for_et, elevation_m=elev_for_et)
        eta_mm = calculate_eta(et0_mm, kc)
        # Convert ETa (mm) over the plant's canopy area to liters of water transpired
        et_liters = max(eta_mm * canopy_m2, 0.0)
    # Ensure we have a valid numeric for et_liters
    if et_liters is None:
        et_liters = 0.0

    # Calculate today's vegetative growth index (VGI)
    base_vgi_today = gdd * par_mj * et_liters
    base_vgi_today = round(base_vgi_today, 2)
    # Apply stage-based growth rate modifier (if defined for this stage)
    growth_factor = 1.0
    if isinstance(stage_data, dict):
        for key in ("growth_factor", "growth_rate_modifier", "growth_modifier"):
            if key in stage_data:
                try:
                    growth_factor = float(stage_data[key])
                except (ValueError, TypeError):
                    growth_factor = 1.0
                break
    if growth_factor == 1.0 and stage_lower in STAGE_GROWTH_MODIFIERS:
        growth_factor = STAGE_GROWTH_MODIFIERS[stage_lower]
    vgi_today = round(base_vgi_today * growth_factor, 2)

    # Prepare to save growth trend data
    data_dir = data_path(hass)
    os.makedirs(data_dir, exist_ok=True)
    trends_path = os.path.join(data_dir, "growth_trends.json")

    # Load existing growth trends file (if any)
    try:
        if os.path.exists(trends_path):
            with open(trends_path, encoding="utf-8") as f:
                growth_trends = json.load(f)
        else:
            growth_trends = {}
    except json.JSONDecodeError:
        _LOGGER.warning("Growth trends file found but not valid JSON, resetting file.")
        growth_trends = {}

    # Ensure data structure for this plant
    if plant_id not in growth_trends or not isinstance(growth_trends[plant_id], dict):
        growth_trends[plant_id] = {}

    # Record today's data point in the time series
    today_str = datetime.now().strftime("%Y-%m-%d")
    growth_trends[plant_id][today_str] = {
        "vgi": vgi_today,
        "gdd": round(gdd, 2),
        "dli": round(dli_mol, 2) if dli_mol is not None else None,
        "par_mj": round(par_mj, 2),
        "et_liters": round(et_liters, 3),
        "stage": stage,
    }

    # Save updated trends to JSON
    try:
        with open(trends_path, "w", encoding="utf-8") as f:
            json.dump(growth_trends, f, indent=2)
    except Exception as e:
        _LOGGER.error("Failed to write growth trends file: %s", e)

    # Compute cumulative metrics for summary
    # Total VGI accumulated (all time)
    total_vgi = 0.0
    for entry in growth_trends[plant_id].values():
        if isinstance(entry, dict) and entry.get("vgi") is not None:
            try:
                total_vgi += float(entry["vgi"])
            except Exception:
                continue
    total_vgi = round(total_vgi, 2)
    days_tracked = len(growth_trends[plant_id])

    # Calculate stage-specific cumulative VGI and progression
    stage_vgi_total = 0.0
    stage_days_count = 0
    # Iterate history in reverse chronological order until a different stage is encountered
    for date_str in sorted(growth_trends[plant_id].keys(), reverse=True):
        entry = growth_trends[plant_id][date_str]
        if not isinstance(entry, dict):
            continue
        if str(entry.get("stage", "")).lower() != stage_lower:
            break  # stop when we hit data from a previous stage
        vgi_val = entry.get("vgi")
        if vgi_val is None:
            vgi_val = 0.0
        try:
            stage_vgi_total += float(vgi_val)
        except Exception:
            stage_vgi_total += 0.0
        stage_days_count += 1
    stage_vgi_total = round(stage_vgi_total, 2)

    # Calculate progression percentages relative to stage expectations
    stage_progress_time_pct = None
    stage_progress_vgi_pct = None
    if stage_duration_days and stage_duration_days > 0:
        # Percentage of stage time elapsed
        stage_progress_time = stage_days_count / float(stage_duration_days)
        stage_progress_time_pct = round(min(stage_progress_time * 100.0, 100.0), 1)
        # Estimate expected total VGI for this stage under ideal conditions
        ideal_temp = IDEAL_ENV_DEFAULT["temp_c"]
        ideal_temp_max = IDEAL_ENV_DEFAULT["temp_c_max"]
        ideal_temp_min = IDEAL_ENV_DEFAULT["temp_c_min"]
        ideal_rh = IDEAL_ENV_DEFAULT["rh_pct"]
        ideal_par_w = IDEAL_ENV_DEFAULT["par"]
        ideal_wind = IDEAL_ENV_DEFAULT["wind_speed_m_s"]
        ideal_elev = IDEAL_ENV_DEFAULT["elevation_m"]
        # Compute GDD under ideal temps
        ideal_gdd = ((ideal_temp_max + ideal_temp_min) / 2) - base_temp_c
        ideal_gdd = max(ideal_gdd, 0.0)
        # Compute PAR in MJ under ideal light
        # Use profile's Kc and canopy for ideal transpiration
        kc = profile.get("general", {}).get("kc", profile.get("kc", 1.0))
        canopy_m2 = profile.get("general", {}).get("canopy_m2", profile.get("canopy_m2", 0.25))
        try:
            kc = float(kc)
        except Exception:
            kc = 1.0
        try:
            canopy_m2 = float(canopy_m2)
        except Exception:
            canopy_m2 = 0.25
        et0_ideal = calculate_et0(ideal_temp, ideal_rh, ideal_par_w, wind_m_s=ideal_wind, elevation_m=ideal_elev)
        eta_ideal = calculate_eta(et0_ideal, kc)
        transp_l_ideal = max(eta_ideal * canopy_m2, 0.0)
        base_vgi_ideal_day = ideal_gdd * (ideal_par_w * 0.0864) * transp_l_ideal  # use ideal PAR (W to MJ)
        base_vgi_ideal_day = max(base_vgi_ideal_day, 0.0)
        # Use same stage growth factor for ideal scenario
        ideal_growth_factor = growth_factor
        vgi_ideal_day = base_vgi_ideal_day * ideal_growth_factor
        expected_stage_vgi_total = vgi_ideal_day * float(stage_duration_days)
        if expected_stage_vgi_total > 0:
            stage_progress_vgi_pct = round(min((stage_vgi_total / expected_stage_vgi_total) * 100.0, 100.0), 1)
        else:
            stage_progress_vgi_pct = 0.0

    # Build summary of today's update
    summary = {
        "plant_id": plant_id,
        "vgi_today": vgi_today,
        "vgi_total": total_vgi,
        "days_tracked": days_tracked,
        "stage": stage,
    }
    if stage_progress_time_pct is not None:
        summary["stage_progress_time_pct"] = stage_progress_time_pct
    if stage_progress_vgi_pct is not None:
        summary["stage_progress_vgi_pct"] = stage_progress_vgi_pct

    _LOGGER.info(
        (
            "Updated growth index for %s: VGI today=%.2f, total=%.2f, stage=%s "
            "(Stage progress: %.1f%% time, %.1f%% growth)"
        ),
        plant_id,
        vgi_today,
        total_vgi,
        stage,
        stage_progress_time_pct if stage_progress_time_pct is not None else 0.0,
        stage_progress_vgi_pct if stage_progress_vgi_pct is not None else 0.0,
    )
    return summary
