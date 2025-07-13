import os
from typing import Dict
from plant_engine.utils import load_json, save_json
from plant_engine.ai_model import analyze
from plant_engine.et_model import calculate_et0, calculate_eta
from plant_engine.compute_transpiration import compute_transpiration
from plant_engine.water_deficit_tracker import update_water_balance
from plant_engine.growth_model import update_growth_index
from plant_engine.nutrient_efficiency import calculate_nue
from plant_engine.approval_queue import queue_threshold_updates

PLANTS_DIR = "plants"
OUTPUT_DIR = "data/reports"

def run_daily_cycle(plant_id: str):
    plant_file = os.path.join(PLANTS_DIR, f"{plant_id}.json")
    profile = load_json(plant_file)

    # Environmental inputs
    env = profile.get("latest_env", {
        "temp_c": 26,
        "temp_c_max": 30,
        "temp_c_min": 22,
        "rh_pct": 65,
        "par": 350,
        "wind_speed_m_s": 1.2
    })

    # Step 1: Transpiration and ET
    transp = compute_transpiration(profile, env)
    transp_ml = transp["transpiration_ml_day"]

    # Step 2: Water balance
    irrigated_ml = profile.get("last_irrigation_ml", 1000)
    water = update_water_balance(plant_id, irrigated_ml, transp_ml)

    # Step 3: Growth index
    growth = update_growth_index(plant_id, env, transp_ml)

    # Step 4: NUE tracking
    try:
        nue = calculate_nue(plant_id)
    except FileNotFoundError:
        nue = {}

    # Step 5: AI Recommendation
    report = {
        "plant_id": plant_id,
        "thresholds": profile.get("thresholds", {}),
        "growth": growth,
        "transpiration": transp,
        "water_deficit": water,
        "nue": nue,
        "lifecycle_stage": profile.get("stage", "unknown"),
        "tags": profile.get("tags", [])
    }

    recommendations = analyze(report)

    # Step 6: Auto-approve or queue
    if profile.get("auto_approve_all", False):
        profile["thresholds"] = recommendations
        save_json(plant_file, profile)
        print(f"✅ Auto-applied AI threshold updates for {plant_id}")
    else:
        queue_threshold_updates(plant_id, profile["thresholds"], recommendations)

    # Step 7: Write daily report JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{plant_id}.json")
    save_json(out_path, report)
    print(f"📄 Daily report saved for {plant_id}")

    return report
