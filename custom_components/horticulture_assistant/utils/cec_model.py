# File: custom_components/horticulture_assistant/utils/cec_model.py
"""CEC (Cation Exchange Capacity) logging and estimation utilities.

This module records measured CEC values for a plant's growing media (in meq/100g) and can estimate CEC from an
inferred media type. It categorizes CEC as low, medium, or high relative to typical crop nutrient retention needs
and can emit warning flags (for example, a low CEC may indicate poor nutrient retention).
"""

import json
import logging
import os

from custom_components.horticulture_assistant.utils.path_utils import data_path

from . import media_inference  # use media_inference.infer_media_type for media-based CEC estimation

_LOGGER = logging.getLogger(__name__)

# Typical CEC (meq/100g) estimates for known media types.
# These values represent approximate cation exchange capacities for common growing media.
MEDIA_CEC_ESTIMATES: dict[str, float] = {
    "Peat Moss": 110.0,  # Peat moss typically has high CEC (e.g., 90-140 meq/100g)
    "Coco Coir": 75.0,  # Coco coir has moderate to high CEC (e.g., 50-100 meq/100g)
    "Rockwool": 1.0,  # Rockwool is virtually inert (CEC ~0 meq/100g)
    "Perlite Blend": 3.0,  # Perlite (often mixed with other media) has very low CEC (1-5 meq/100g)
}


def _write_cec_record(output_path: str, plant_id: str | None, result_data: dict):
    """Internal helper to write CEC data to JSON file."""
    try:
        # Load existing data if present
        if os.path.exists(output_path):
            with open(output_path, encoding="utf-8") as f:
                all_results = json.load(f)
        else:
            all_results = {}
    except Exception as err:
        _LOGGER.error("Could not read %s: %s. Starting fresh.", output_path, err)
        all_results = {}
    # Ensure we have a dictionary to update (reset if not)
    if not isinstance(all_results, dict):
        all_results = {}
    if plant_id:
        # Store or update this plant's CEC record
        all_results[str(plant_id)] = result_data
        data_to_write = all_results
    else:
        # No plant_id given: overwrite file with this single result
        data_to_write = result_data
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data_to_write, f, indent=2)
    except Exception as err:
        _LOGGER.error("Failed to write CEC record to %s: %s", output_path, err)


def log_measured_cec(plant_id: str, cec_value: float, include_warnings: bool = False) -> dict | None:
    """Log an observed/measured CEC value for a plant's growth media.

    Parameters:
      - plant_id: Unique identifier for the plant.
      - cec_value: Measured CEC (in meq/100g) of the plant's growing media.
      - include_warnings: If True, include nutrient retention warning flags in the record (e.g., if CEC is low).

    Returns a dictionary with the recorded CEC data (including source and optional warning/category),
    and saves this record to data/cec_records.json under the given plant_id.
    """
    try:
        cec_val = float(cec_value)
    except (TypeError, ValueError) as err:
        _LOGGER.error("Invalid CEC value provided for plant %s: %s", plant_id, err)
        return None
    if cec_val < 0:
        _LOGGER.warning("CEC value for plant %s is negative (%s); setting to 0.", plant_id, cec_val)
        cec_val = 0.0
    # Prepare the record data
    result_data: dict[str, float | None] = {"cec": round(cec_val, 2), "source": "measured"}
    if include_warnings:
        # Determine category and potential nutrient retention issues
        category = categorize_cec(cec_val)
        if category == "Low":
            result_data["warning"] = "Low nutrient retention (CEC is low for most crops)"
        elif category == "High":
            result_data["warning"] = "High nutrient retention (CEC is high; monitor nutrient buildup)"
        # Include category label for reference
        result_data["category"] = category
    # Write to JSON records
    output_path = data_path(None, "cec_records.json")
    _write_cec_record(output_path, plant_id, result_data)
    _LOGGER.info("Logged measured CEC for plant %s: %.2f meq/100g", plant_id, cec_val)
    return result_data


def estimate_cec_from_media(
    plant_id: str,
    moisture_retention: float,
    ec_behavior: float,
    dryback_rate: float,
    include_warnings: bool = False,
) -> dict | None:
    """Estimate the CEC for a plant's growth media based on media type inference.

    This uses characteristic sensor patterns (moisture retention, EC buffering, dryback rate) to infer the media type
    via media_inference.infer_media_type, then assigns a typical CEC value for that media type.

    Parameters:
      - plant_id: Unique identifier for the plant (used for record logging).
      - moisture_retention: Observed relative water-holding metric (0-1 scale or percentage).
      - ec_behavior: Observed nutrient/EC buffering metric (0-1 scale or percentage).
      - dryback_rate: Observed drying speed metric (0-1 scale or percentage).
      - include_warnings: If True, include nutrient retention warning flags (for example, when estimated CEC is low).

    Returns a dictionary with the estimated CEC data (including source, media_type, confidence, and optional warning/
    category), and saves this record to data/cec_records.json under the given plant_id. If inference fails or media type
    is unknown, returns None.
    """
    # Use media_inference to get likely media type
    media_result = media_inference.infer_media_type(moisture_retention, ec_behavior, dryback_rate, plant_id=plant_id)
    if not media_result:
        _LOGGER.error("Media type inference failed; cannot estimate CEC for plant %s.", plant_id)
        return None
    media_type = media_result.get("media_type")
    confidence = media_result.get("confidence", 0.0)
    if not media_type or media_type not in MEDIA_CEC_ESTIMATES:
        _LOGGER.error(
            "Unknown media type '%s' inferred for plant %s; CEC estimation not available.",
            media_type,
            plant_id,
        )
        return None
    estimated_cec = MEDIA_CEC_ESTIMATES[media_type]
    # Prepare the record data
    result_data: dict[str, float | None] = {
        "cec": round(estimated_cec, 2),
        "source": "estimated",
        "media_type": media_type,
        "confidence": round(confidence, 3),
    }
    if include_warnings:
        category = categorize_cec(estimated_cec)
        if category == "Low":
            result_data["warning"] = "Low nutrient retention (CEC is low for most crops)"
        elif category == "High":
            result_data["warning"] = "High nutrient retention (CEC is high; monitor nutrient buildup)"
        result_data["category"] = category
    # Write to JSON records
    output_path = data_path(None, "cec_records.json")
    _write_cec_record(output_path, plant_id, result_data)
    _LOGGER.info(
        "Estimated CEC for plant %s: %.2f meq/100g (media: %s, confidence: %.3f)",
        plant_id,
        estimated_cec,
        media_type,
        confidence,
    )
    return result_data


def categorize_cec(cec_value: float) -> str:
    """Categorize a CEC value as "Low", "Medium", or "High" for nutrient retention.

    Low CEC indicates the growing medium has low nutrient retention capacity (common in sandy or inert media).
    Medium CEC indicates moderate nutrient retention (typical of loam or mixed media).
    High CEC indicates high nutrient retention capacity (common in organic-rich or clay media, suitable for
    nutrient-demanding crops).

    These categories are general; specific crop requirements might adjust what is considered low or high for a given
    plant.
    """
    try:
        cec_val = float(cec_value)
    except (TypeError, ValueError):
        # If value is not convertible to float, return empty string
        return ""
    if cec_val < 0:
        cec_val = 0.0
    # Define threshold cutoffs (meq/100g) for low/medium/high categories.
    # These thresholds can be adjusted if specific crop requirements are known.
    if cec_val < 10.0:
        return "Low"
    elif cec_val < 20.0:
        return "Medium"
    else:
        return "High"
