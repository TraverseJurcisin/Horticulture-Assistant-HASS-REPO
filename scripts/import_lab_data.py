import os
from datetime import datetime
from plant_engine.utils import load_json, save_json
from plant_engine.approval_queue import queue_threshold_updates

LAB_DATA_DIR = "data/lab_tests"

def import_lab_test(plant_id: str, lab_file_path: str, test_type: str = "tissue"):
    """
    Ingest a lab result JSON (tissue/media/water) and compare against current thresholds.
    Proposes updated thresholds if values deviate from acceptable ranges.
    """
    assert test_type in ["tissue", "media", "water"]

    plant_path = f"plants/{plant_id}.json"
    profile = load_json(plant_path)
    thresholds = profile.get("thresholds", {})
    lifecycle = profile.get("stage", "unknown")

    with open(lab_file_path, "r", encoding="utf-8") as f:
        lab_data = load_json(f)

    proposed = {}
    for nutrient, value in lab_data.items():
        if nutrient not in thresholds:
            continue

        expected = thresholds[nutrient]
        deviation = (value - expected) / expected

        if abs(deviation) > 0.25:  # 25% deviation triggers proposal
            new_value = round((value + expected) / 2, 2)
            proposed[nutrient] = new_value

    if proposed:
        print(f"🧪 {test_type.capitalize()} test detected deviations. Queuing updates:")
        for k, v in proposed.items():
            print(f"  - {k}: {thresholds[k]} ➜ {v}")

        queue_threshold_updates(plant_id, thresholds, proposed)

    else:
        print(f"✅ All nutrient values within acceptable range for {plant_id}")

    # Save raw test for record
    os.makedirs(LAB_DATA_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    test_out = os.path.join(LAB_DATA_DIR, f"{plant_id}_{test_type}_{timestamp}.json")
    save_json(test_out, lab_data)
    print(f"📁 Lab file archived at {test_out}")
