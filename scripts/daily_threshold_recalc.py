import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# === CONFIGURATION ===

PLANT_REGISTRY_PATH = "plant_registry.json"
PLANT_PROFILE_DIR = "plants"
DAILY_REPORT_DIR = "data/daily_reports"
AUTO_APPROVE_FIELD = "auto_approve_all"


# === HELPER FUNCTIONS ===

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def generate_daily_report(plant_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock version of AI input data packaging.
    This would eventually query live sensor data (via Home Assistant API or InfluxDB).
    """
    now = datetime.now()
    return {
        "plant_id": plant_id,
        "timestamp": now.isoformat(),
        "lifecycle_stage": profile.get("lifecycle_stage"),
        "sensor_entities": profile.get("sensor_entities"),
        "thresholds": profile.get("thresholds"),
        "tags": profile.get("tags", []),
        "yield": profile.get("last_yield", None),
        "ai_feedback_required": not profile.get(AUTO_APPROVE_FIELD, False)
    }


def mock_threshold_adjustments(thresholds: Dict[str, float]) -> Dict[str, float]:
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


def update_plant_profile(plant_path: str, updated_thresholds: Dict[str, float]) -> None:
    profile = load_json(plant_path)
    profile["thresholds"] = updated_thresholds
    save_json(plant_path, profile)


# === MAIN ORCHESTRATOR ===

def run_daily_threshold_updates():
    print("🚀 Starting daily threshold recalculation...")

    plant_registry = load_json(PLANT_REGISTRY_PATH)

    for plant_id, meta in plant_registry.items():
        print(f"\n🌿 Processing plant: {plant_id}")
        profile_path = meta["profile_path"]

        if not os.path.exists(profile_path):
            print(f"❌ Profile not found: {profile_path}")
            continue

        profile = load_json(profile_path)
        report = generate_daily_report(plant_id, profile)

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
        

        if profile.get(AUTO_APPROVE_FIELD, False):
            update_plant_profile(profile_path, new_thresholds)
            print("✅ Thresholds auto-updated (auto_approve_all: true)")
        else:
            print("🛑 Awaiting manual approval for threshold updates")

    print("\n✅ Daily threshold recalculation complete.")


# === ENTRY POINT ===

if __name__ == "__main__":
    run_daily_threshold_updates()
