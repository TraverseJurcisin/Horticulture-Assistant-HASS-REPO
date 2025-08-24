import os

from approval_queue import apply_approved_thresholds
from plant_engine.utils import get_pending_dir, load_json, save_json

PENDING_DIR = str(get_pending_dir())
PLANT_DIR = "plants"


def review_pending_thresholds():
    print("🔍 Scanning for pending threshold files...\n")

    for fname in os.listdir(PENDING_DIR):
        if not fname.endswith(".json"):
            continue

        full_path = os.path.join(PENDING_DIR, fname)
        pending = load_json(full_path)
        plant_id = pending["plant_id"]
        changes = pending["changes"]

        if not changes:
            print(f"🟡 No pending changes in {fname}")
            continue

        print(f"\n🌱 Reviewing thresholds for: {plant_id}")

        for nutrient, change in changes.items():
            status = change.get("status", "pending")
            if status != "pending":
                continue

            prev = change["previous_value"]
            proposed = change["proposed_value"]
            print(f"\n🔸 {nutrient}")
            print(f"    Previous: {prev}")
            print(f"    Proposed: {proposed}")
            decision = input("Approve [y], Reject [n], Skip [s]? ").lower()

            if decision == "y":
                change["status"] = "approved"
            elif decision == "n":
                change["status"] = "rejected"
            else:
                print("⏭️  Skipping.")

        # Save modified file
        save_json(full_path, pending)
        print("📁 Updated pending file.")

        # Apply changes if any approved
        if any(v["status"] == "approved" for v in changes.values()):
            plant_path = os.path.join(PLANT_DIR, f"{plant_id}.json")
            apply_approved_thresholds(plant_path, full_path)

    print("\n✅ Review complete.")


if __name__ == "__main__":
    review_pending_thresholds()
