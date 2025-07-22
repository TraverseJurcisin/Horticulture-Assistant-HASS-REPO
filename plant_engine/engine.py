import os
from typing import Dict
from plant_engine.utils import load_json, save_json
from plant_engine.ai_model import analyze
from plant_engine.compute_transpiration import compute_transpiration
from plant_engine.water_deficit_tracker import update_water_balance
from plant_engine.growth_model import update_growth_index
from plant_engine.rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
)
from plant_engine.nutrient_efficiency import calculate_nue
from plant_engine.approval_queue import queue_threshold_updates
from plant_engine.environment_manager import (
    recommend_environment_adjustments,
    optimize_environment,
)
from plant_engine.nutrient_manager import get_recommended_levels
from plant_engine.pest_manager import recommend_treatments as recommend_pest_treatments
from plant_engine.disease_manager import recommend_treatments as recommend_disease_treatments
from plant_engine.growth_stage import get_stage_info

PLANTS_DIR = "plants"
OUTPUT_DIR = "data/reports"

# Basic multipliers to scale nutrient recommendations by growth stage
STAGE_MULTIPLIERS = {
    "seedling": 0.5,
    "vegetative": 1.0,
    "flowering": 1.2,
    "fruiting": 1.1,
}

def run_daily_cycle(plant_id: str) -> Dict:
    """Run a full daily processing cycle for a plant profile."""
    plant_file = os.path.join(PLANTS_DIR, f"{plant_id}.json")
    profile = load_json(plant_file)

    # Environmental inputs
    env = profile.get(
        "latest_env",
        {
            "temp_c": 26,
            "temp_c_max": 30,
            "temp_c_min": 22,
            "rh_pct": 65,
            "par_w_m2": 350,
            "wind_speed_m_s": 1.2,
        },
    )

    # Step 1: Transpiration and ET
    transp = compute_transpiration(profile, env)
    transp_ml = transp["transpiration_ml_day"]

    # Step 2: Environmental actions
    env_actions = recommend_environment_adjustments(
        env, profile.get("plant_type", ""), profile.get("stage")
    )
    pest_actions = recommend_pest_treatments(
        profile.get("plant_type", ""), profile.get("observed_pests", [])
    )
    disease_actions = recommend_disease_treatments(
        profile.get("plant_type", ""), profile.get("observed_diseases", [])
    )

    # Step 3: Growth index
    growth = update_growth_index(plant_id, env, transp_ml)

    root_depth = estimate_rootzone_depth(profile, growth)
    rootzone = estimate_water_capacity(
        root_depth,
        texture=profile.get("soil_texture"),
    )

    # Step 4: Water balance
    irrigated_ml = profile.get("last_irrigation_ml", 1000)
    water = update_water_balance(
        plant_id,
        irrigated_ml,
        transp_ml,
        rootzone_ml=rootzone.total_available_water_ml,
        mad_pct=rootzone.mad_pct,
    )

    # Step 5: NUE tracking
    try:
        nue = calculate_nue(plant_id)
    except FileNotFoundError:
        nue = {}

    # Step 6: Recommended nutrient levels
    guidelines = get_recommended_levels(
        profile.get("plant_type", ""),
        profile.get("stage", "")
    )

    stage_name = str(profile.get("stage", "")).lower()
    stage_mult = STAGE_MULTIPLIERS.get(stage_name, 1.0)
    nutrient_targets = {
        n: round(v * stage_mult, 2) for n, v in guidelines.items()
    } if guidelines else {}

    env_current = {}
    if env.get("temp_c") is not None:
        env_current["temp_c"] = env.get("temp_c")
    if env.get("rh_pct") is not None:
        env_current["humidity_pct"] = env.get("rh_pct")
    if env.get("par_w_m2") is not None:
        env_current["light_ppfd"] = env.get("par_w_m2")
    if env.get("co2_ppm") is not None:
        env_current["co2_ppm"] = env.get("co2_ppm")
    env_opt = optimize_environment(
        env_current, profile.get("plant_type", ""), profile.get("stage")
    )

    stage_info = get_stage_info(
        profile.get("plant_type", ""), profile.get("stage", "")
    )

    # Step 7: AI Recommendation
    report = {
        "plant_id": plant_id,
        "thresholds": profile.get("thresholds", {}),
        "growth": growth,
        "transpiration": transp,
        "water_deficit": water,
        "rootzone": rootzone.to_dict(),
        "nue": nue,
        "guidelines": guidelines,
        "nutrient_targets": nutrient_targets,
        "environment_actions": env_actions,
        "environment_optimization": env_opt,
        "pest_actions": pest_actions,
        "disease_actions": disease_actions,
        "lifecycle_stage": profile.get("stage", "unknown"),
        "stage_info": stage_info,
        "tags": profile.get("tags", [])
    }

    recommendations = analyze(report)

    # Step 8: Auto-approve or queue
    if profile.get("auto_approve_all", False):
        profile["thresholds"] = recommendations
        save_json(plant_file, profile)
        print(f"✅ Auto-applied AI threshold updates for {plant_id}")
    else:
        queue_threshold_updates(plant_id, profile["thresholds"], recommendations)

    # Step 9: Write daily report JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{plant_id}.json")
    save_json(out_path, report)
    print(f"📄 Daily report saved for {plant_id}")

    return report
