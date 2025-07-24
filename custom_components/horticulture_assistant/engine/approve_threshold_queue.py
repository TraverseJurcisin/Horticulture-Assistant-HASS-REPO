import os
import json
import logging
import re
try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # if Home Assistant not available, ignore for standalone use

_LOGGER = logging.getLogger(__name__)

def approve_threshold_queue(hass: "HomeAssistant" = None) -> None:
    """
    Scan pending threshold change files and interactively approve or reject changes.
    For each pending threshold change in data/pending_thresholds, prompt user (y/n/s) and update status.
    Approved changes are applied to the plant's profile (thresholds) and all actions are logged.
    """
    base_data_dir = hass.config.path("data") if hass else "data"
    base_plants_dir = hass.config.path("plants") if hass else "plants"
    pending_dir = os.path.join(base_data_dir, "pending_thresholds")
    # Pattern for pending threshold files: {plant_id}_YYYY-MM-DD.json
    file_pattern = re.compile(r"^.+_\d{4}-\d{2}-\d{2}\.json$")
    if not os.path.isdir(pending_dir):
        _LOGGER.info("Pending thresholds directory not found at %s; no changes to approve.", pending_dir)
        print(f"No pending thresholds directory found at {pending_dir}.")
        return
    # Gather all JSON files matching the pattern
    files = sorted(f for f in os.listdir(pending_dir) if file_pattern.match(f))
    if not files:
        _LOGGER.info("No pending threshold update files found in %s.", pending_dir)
        print("No pending threshold changes to approve.")
        return
    total_approved = 0
    total_rejected = 0
    total_skipped = 0
    for filename in files:
        file_path = os.path.join(pending_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            _LOGGER.error("Pending threshold file not found: %s", file_path)
            print(f"Pending threshold file not found: {filename}")
            continue
        except json.JSONDecodeError as e:
            _LOGGER.error("Failed to parse pending threshold file %s: %s", filename, e)
            print(f"Error reading {filename}: invalid JSON.")
            continue
        plant_id = data.get("plant_id", "unknown")
        changes = data.get("changes")
        if not changes or not any(info.get("status") == "pending" for info in changes.values()):
            _LOGGER.info("No pending threshold changes in file %s; skipping.", filename)
            # No pending entries to approve in this file
            continue
        print(f"\nReviewing pending threshold changes for plant '{plant_id}' (file: {filename}):")
        file_modified = False
        any_rejected = False
        approved_list = []
        # Iterate through each pending change in this file
        for param, info in changes.items():
            if info.get("status") != "pending":
                continue  # skip already processed changes
            old_val = info.get("previous_value")
            new_val = info.get("proposed_value")
            print(f" - {param}: {old_val} -> {new_val} (pending)")
            # Prompt user for approval decision
            while True:
                choice = input("Approve this change? [y]es/[n]o/[s]kip: ").strip().lower()
                if choice in ("y", "n", "s", ""):
                    break
                print("Invalid input. Please enter 'y', 'n', or 's'.")
            if choice == "y":
                info["status"] = "approved"
                file_modified = True
                approved_list.append(param)
                total_approved += 1
                _LOGGER.info("User approved threshold change for plant %s: %s from %s to %s", plant_id, param, old_val, new_val)
                print("Approved.")
            elif choice == "n":
                info["status"] = "rejected"
                file_modified = True
                any_rejected = True
                total_rejected += 1
                _LOGGER.info("User rejected threshold change for plant %s: %s from %s to %s", plant_id, param, old_val, new_val)
                print("Rejected.")
            else:
                # Skip (either "s" or empty input)
                total_skipped += 1
                _LOGGER.info("User skipped threshold change for plant %s: %s (still pending)", plant_id, param)
                print("Skipped.")
        # End for each pending change
        if not file_modified:
            # No changes were approved or rejected (all skipped)
            _LOGGER.info("No changes made to pending threshold file %s (all changes left pending).", filename)
            continue
        profile_update_failed = False
        if approved_list:
            # Attempt to apply approved changes to the plant's profile
            plant_file_path = os.path.join(base_plants_dir, f"{plant_id}.json")
            try:
                with open(plant_file_path, "r", encoding="utf-8") as pf:
                    profile = json.load(pf)
            except FileNotFoundError:
                _LOGGER.error("Plant profile file not found for '%s' at %s; cannot apply approved changes now.", plant_id, plant_file_path)
                print(f"Warning: profile for plant '{plant_id}' not found. Approved changes will remain pending.")
                profile_update_failed = True
            except json.JSONDecodeError as e:
                _LOGGER.error("Failed to read profile for plant '%s': %s; skipping its changes.", plant_id, e)
                print(f"Warning: profile for plant '{plant_id}' is invalid. Approved changes will remain pending.")
                profile_update_failed = True
            else:
                # Ensure thresholds section exists and is a dict
                thresholds = profile.get("thresholds")
                if thresholds is None or not isinstance(thresholds, dict):
                    _LOGGER.warning("Thresholds section missing or invalid in profile %s; resetting to empty dict.", plant_id)
                    thresholds = {}
                for param in approved_list:
                    change_info = changes.get(param)
                    if not change_info or change_info.get("status") != "approved":
                        continue
                    old_val = change_info.get("previous_value")
                    new_val = change_info.get("proposed_value")
                    thresholds[param] = new_val
                    _LOGGER.info("Applied approved threshold change for plant %s: %s from %s to %s", plant_id, param, old_val, new_val)
                profile["thresholds"] = thresholds
                try:
                    os.makedirs(os.path.dirname(plant_file_path), exist_ok=True)
                    with open(plant_file_path, "w", encoding="utf-8") as pf:
                        json.dump(profile, pf, indent=2)
                except Exception as e:
                    _LOGGER.error("Failed to write updated profile for plant '%s': %s", plant_id, e)
                    print(f"Warning: could not write profile for plant '{plant_id}'. Approved changes will remain pending.")
                    profile_update_failed = True
                else:
                    _LOGGER.info("Updated plant %s profile with %d approved change(s).", plant_id, len(approved_list))
        # If profile update failed, revert any approved statuses back to pending
        if profile_update_failed and approved_list:
            for param in approved_list:
                # Only revert if it is still marked approved
                if changes.get(param) and changes[param].get("status") == "approved":
                    changes[param]["status"] = "pending"
            _LOGGER.warning("Reverted %d approved change(s) for plant %s to pending due to profile update failure.", len(approved_list), plant_id)
            # Adjust global counters for reverted approvals
            total_skipped += len(approved_list)
            total_approved -= len(approved_list)
            # If no other changes (e.g., no rejections) in this file, then nothing changed after all
            if not any_rejected:
                file_modified = False
        # Write the updated pending file (with new statuses)
        if file_modified:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                _LOGGER.error("Failed to write updated pending threshold file %s: %s", filename, e)
                print(f"Error: failed to update pending file {filename}. Changes may not be saved.")
    # End for each file
    _LOGGER.info("Threshold approval review complete: %d approved, %d rejected, %d skipped.", total_approved, total_rejected, total_skipped)
    print(f"\nReview complete. Approved: {total_approved}, Rejected: {total_rejected}, Skipped: {total_skipped}.")

if __name__ == "__main__":
    approve_threshold_queue()
