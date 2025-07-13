import os
from plant_engine import run_daily_cycle
from plant_engine.utils import load_json, save_json

PLANT_DIR = "plants"
SUMMARY_PATH = "data/reports/summary.json"

def get_plant_ids():
    return [
        f.replace(".json", "")
        for f in os.listdir(PLANT_DIR)
        if f.endswith(".json")
    ]

def run_all_plants():
    summary = {}

    for plant_id in get_plant_ids():
        print(f"🔄 Running daily engine for: {plant_id}")
        try:
            report = run_daily_cycle(plant_id)
            summary[plant_id] = report
        except Exception as e:
            summary[plant_id] = {"error": str(e)}
            print(f"❌ Error processing {plant_id}: {e}")

    # Save master report
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    save_json(SUMMARY_PATH, summary)
    print(f"\n✅ Summary report written to {SUMMARY_PATH}")

if __name__ == "__main__":
    run_all_plants()
