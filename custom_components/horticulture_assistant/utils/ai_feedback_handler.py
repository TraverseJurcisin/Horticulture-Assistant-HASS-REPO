import os
import json
import logging
from datetime import datetime

from plant_engine import ai_model
from ..const import (
    CONF_OPENAI_API_KEY,
    CONF_OPENAI_MODEL,
    CONF_USE_OPENAI,
    CONF_OPENAI_TEMPERATURE,
)
from . import global_config
from custom_components.horticulture_assistant.utils.path_utils import (
    plants_path,
    data_path,
)

_LOGGER = logging.getLogger(__name__)


"""Utility for applying AI generated threshold feedback to plant profiles."""

def process_ai_feedback(plant_id: str, daily_report: dict) -> str:
    """
    Process a plant's daily report with AI to get new threshold recommendations and advice.
    If auto_approve is True, update the plant's profile JSON immediately with new thresholds.
    If auto_approve is False, save the recommendation to a pending approvals queue.
    Returns the advice string generated for logging or UI purposes.
    """
    # Validate inputs
    if not plant_id or not isinstance(daily_report, dict):
        _LOGGER.error("Invalid inputs to process_ai_feedback: plant_id=%s, daily_report type=%s",
                      plant_id, type(daily_report))
        return ""
    # Optional: ensure the report is for the correct plant
    report_plant = daily_report.get("plant_id")
    if report_plant and report_plant != plant_id:
        _LOGGER.warning("Plant ID mismatch: got report for '%s' but expected '%s'", report_plant, plant_id)
    # Ensure thresholds key exists in report
    if "thresholds" not in daily_report:
        _LOGGER.warning("Daily report for plant %s is missing 'thresholds' data", plant_id)
        daily_report["thresholds"] = {}
    # Call AI model to analyze the report using global settings
    cfg = global_config.load_config()
    model_cfg = ai_model.AIModelConfig(
        use_openai=cfg.get(CONF_USE_OPENAI, ai_model.USE_OPENAI),
        model=cfg.get(CONF_OPENAI_MODEL, ai_model.OPENAI_MODEL),
        api_key=cfg.get(CONF_OPENAI_API_KEY) or ai_model.OPENAI_API_KEY,
        temperature=cfg.get(CONF_OPENAI_TEMPERATURE, ai_model.OPENAI_TEMPERATURE),
    )
    try:
        result = ai_model.analyze(daily_report, model_cfg)
    except Exception as e:
        _LOGGER.error("AI model analysis failed for plant %s: %s", plant_id, e)
        return ""
    # Determine the new threshold recommendations and any advice from the AI result
    if result is None:
        _LOGGER.error("AI model returned no result for plant %s", plant_id)
        return ""
    if isinstance(result, dict):
        if "thresholds" in result:
            new_thresholds = result.get("thresholds")
            advice_text = result.get("advice", "")
        else:
            # If the AI returned just a dict of thresholds (no explicit wrapper)
            new_thresholds = result
            advice_text = ""
    else:
        _LOGGER.error("Unexpected AI model output for plant %s: %s", plant_id, result)
        return ""
    if not isinstance(new_thresholds, dict):
        _LOGGER.error("AI model returned invalid thresholds for plant %s: %s", plant_id, new_thresholds)
        return ""
    _LOGGER.info("AI threshold recommendations generated for plant %s", plant_id)
    _LOGGER.debug("Recommended thresholds: %s", new_thresholds)
    # Determine auto-approve setting (from report or profile)
    # The daily_report may include a flag indicating whether feedback requires approval
    auto_approve = False
    if daily_report.get("ai_feedback_required") is not None:
        auto_approve = not daily_report.get("ai_feedback_required", True)
    else:
        # Fallback: check plant profile for an auto_approve flag
        profile_path = plants_path(None, f"{plant_id}.json")
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as pf:
                    profile_data = json.load(pf)
                auto_approve = profile_data.get("auto_approve_all", False)
            except Exception as err:
                _LOGGER.error("Could not read profile for plant %s to determine auto_approve: %s", plant_id, err)
                auto_approve = False
    advice = advice_text.strip() if isinstance(advice_text, str) else ""
    # Compute differences between current and new thresholds
    old_thresholds = daily_report.get("thresholds", {})
    changes = {}
    for key, new_val in new_thresholds.items():
        old_val = old_thresholds.get(key)
        # Only record changes where the value differs
        if old_val != new_val:
            changes[key] = {
                "previous_value": old_val,
                "proposed_value": new_val,
                "status": "pending"
            }
    # Apply or queue changes based on auto_approve
    if auto_approve:
        # Auto-approve: apply changes directly to the plant's profile
        profile_path = plants_path(None, f"{plant_id}.json")
        if not os.path.exists(profile_path):
            _LOGGER.error("Plant profile not found at %s; cannot auto-apply thresholds", profile_path)
        else:
            try:
                with open(profile_path, "r", encoding="utf-8") as pf:
                    profile = json.load(pf)
            except Exception as err:
                _LOGGER.error("Failed to load profile for plant %s: %s", plant_id, err)
                profile = None
            if profile is not None:
                profile["thresholds"] = new_thresholds
                try:
                    os.makedirs(os.path.dirname(profile_path), exist_ok=True)
                    with open(profile_path, "w", encoding="utf-8") as pf:
                        json.dump(profile, pf, indent=2)
                    _LOGGER.info("Auto-approved and updated thresholds for plant %s", plant_id)
                except Exception as err:
                    _LOGGER.error("Failed to save updated profile for plant %s: %s", plant_id, err)
        # If no advice text was given by AI, generate a simple note for auto-approval
        if not advice:
            if changes:
                advice = f"Thresholds auto-updated ({len(changes)} changes applied)."
            else:
                advice = "No threshold adjustments needed."
    else:
        # Manual approval mode: queue changes for review
        if changes:
            # Prepare pending approvals record
            record = {
                "plant_id": plant_id,
                "timestamp": datetime.now().isoformat(),
                "changes": changes
            }
            # Load existing pending approvals
            pending_path = data_path(None, "pending_approvals.json")
            try:
                if os.path.exists(pending_path):
                    with open(pending_path, "r", encoding="utf-8") as pf:
                        pending_data = json.load(pf)
                else:
                    pending_data = {}
            except Exception as err:
                _LOGGER.error("Could not read existing pending approvals file: %s. Resetting it.", err)
                pending_data = {}
            # Update pending approvals with this plant's record
            if isinstance(pending_data, dict):
                pending_data[plant_id] = record
            else:
                # If file was not a dict, replace it with a dict
                pending_data = {plant_id: record}
            try:
                os.makedirs(os.path.dirname(pending_path), exist_ok=True)
                with open(pending_path, "w", encoding="utf-8") as pf:
                    json.dump(pending_data, pf, indent=2)
                _LOGGER.info("Queued %d threshold change(s) for plant %s awaiting approval", len(changes), plant_id)
            except Exception as err:
                _LOGGER.error("Failed to write pending approvals for plant %s: %s", plant_id, err)
            # If no AI-provided advice, generate a summary for pending approval
            if not advice:
                if len(changes) == 1:
                    # Describe the single change
                    k, v = next(iter(changes.items()))
                    prev = v["previous_value"]
                    new = v["proposed_value"]
                    advice = f"Threshold '{k}' change proposed: {prev} -> {new} (awaiting approval)."
                else:
                    advice = f"{len(changes)} threshold changes proposed (awaiting approval)."
        else:
            _LOGGER.info("No threshold changes for plant %s; nothing to queue for approval", plant_id)
            if not advice:
                advice = "No threshold changes recommended."
    # Log the advice and return it
    _LOGGER.debug("Advice for plant %s: %s", plant_id, advice)
    return advice
