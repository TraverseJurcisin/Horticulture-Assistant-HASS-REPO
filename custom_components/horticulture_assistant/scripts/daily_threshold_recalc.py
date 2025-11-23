import os
from datetime import datetime
from typing import Any

from ..engine.plant_engine.utils import load_json, save_json
from ..engine.plant_engine.water_deficit_tracker import update_water_balance
from ..profile.compat import sync_thresholds
from ..utils.load_bio_profile import load_bio_profile

# === CONFIGURATION ===

PLANT_REGISTRY_PATH = "data/local/plants/plant_registry.json"
PLANT_PROFILE_DIR = "plants"
DAILY_REPORT_DIR = "data/daily_reports"
AUTO_APPROVE_FIELD = "auto_approve_all"


# === HELPER FUNCTIONS ===
def generate_daily_report(plant_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Return a simple report dictionary for ``plant_id`` based on ``profile``."""

    now = datetime.now()

    general = profile.get("general", profile)

    # Aggregate thresholds from possible sections
    thresholds = profile.get("thresholds")
    if thresholds is None:
        thresholds = {}
        for section in ("irrigation", "nutrition"):
            if section in profile and isinstance(profile[section], dict):
                thresholds.update(profile[section])

    return {
        "plant_id": plant_id,
        "timestamp": now.isoformat(),
        "lifecycle_stage": general.get("lifecycle_stage"),
        "sensor_entities": general.get("sensor_entities"),
        "thresholds": thresholds,
        "tags": general.get("tags", []),
        "yield": general.get("last_yield"),
        "ai_feedback_required": not general.get(AUTO_APPROVE_FIELD, False),
    }


def mock_threshold_adjustments(thresholds: dict[str, float]) -> dict[str, float]:
    """
    Placeholder: adjust thresholds based on arbitrary logic.
    Future: replace with AI model call.
    """
    adjusted = {}
    for nutrient, value in thresholds.items():
        if "leaf_" in nutrient:
            # Example logic: bump target up by 5% during fruiting stage
            adjusted[nutrient] = round(value * 1.05, 2)
        else:
            adjusted[nutrient] = value
    return adjusted


def update_plant_profile(plant_path: str, updated_thresholds: dict[str, float]) -> None:
    """Write ``updated_thresholds`` back to the profile file(s)."""

    if os.path.isdir(plant_path):
        irr_path = os.path.join(plant_path, "irrigation.json")
        nut_path = os.path.join(plant_path, "nutrition.json")
        irrigation = load_json(irr_path) if os.path.exists(irr_path) else {}
        nutrition = load_json(nut_path) if os.path.exists(nut_path) else {}
        if "soil_moisture_pct" in updated_thresholds:
            irrigation["soil_moisture_pct"] = updated_thresholds.pop("soil_moisture_pct")
        nutrition.update(updated_thresholds)
        save_json(irr_path, irrigation)
        save_json(nut_path, nutrition)
    else:
        profile = load_json(plant_path)
        profile["thresholds"] = updated_thresholds
        sync_thresholds(profile, default_source="automation")
        save_json(plant_path, profile)


# === MAIN ORCHESTRATOR ===


def run_daily_threshold_updates():
    print("🚀 Starting daily threshold recalculation...")

    plant_registry = load_json(PLANT_REGISTRY_PATH)

    for plant_id, meta in plant_registry.items():
        print(f"\n🌿 Processing plant: {plant_id}")
        profile_path = meta["profile_path"]

        if os.path.isdir(profile_path):
            profile_obj = load_bio_profile(plant_id, base_path=PLANT_PROFILE_DIR)
            if not profile_obj:
                print(f"❌ Profile not found: {profile_path}")
                continue
            profile = profile_obj.profile_data
        else:
            if not os.path.exists(profile_path):
                print(f"❌ Profile not found: {profile_path}")
                continue
            profile = load_json(profile_path)
        # Step 1: Generate base report
        report = generate_daily_report(plant_id, profile)

        # Step 2: Transpiration estimation
        # (Assumes you've already run compute_transpiration.py elsewhere — otherwise simulate)
        transpiration_ml = report.get("transpiration_ml_day", 1200.0)
        irrigation_ml = report.get("last_irrigation_ml", 1000.0)

        # Step 3: Update water balance tracker
        water_status = update_water_balance(plant_id, irrigation_ml, transpiration_ml)
        report["water_deficit"] = water_status.as_dict()

        # Save daily report to disk
        date_str = datetime.now().strftime("%Y%m%d")
        report_path = os.path.join(DAILY_REPORT_DIR, f"{plant_id}-{date_str}.json")
        save_json(report_path, report)
        print(f"📝 Report saved: {report_path}")

        # Simulate AI threshold recalculation
        from ai_model import analyze
        from approval_queue import queue_threshold_updates

        new_thresholds = analyze(report)

        if profile.get(AUTO_APPROVE_FIELD, False):
            update_plant_profile(profile_path, new_thresholds)
            print("✅ Thresholds auto-updated (auto_approve_all: true)")
        else:
            queue_threshold_updates(plant_id, profile["thresholds"], new_thresholds)
            print("🛑 Threshold changes queued for approval.")

    print("\n✅ Daily threshold recalculation complete.")


# === ENTRY POINT ===

if __name__ == "__main__":
    run_daily_threshold_updates()
