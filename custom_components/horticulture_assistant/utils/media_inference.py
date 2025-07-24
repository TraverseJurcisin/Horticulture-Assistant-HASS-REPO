# File: custom_components/horticulture_assistant/utils/media_inference.py
"""Media type inference module for Horticulture Assistant.

This module provides functionality to estimate the growing media type (e.g., peat moss, coco coir, rockwool, perlite blend) 
based on observed sensor patterns of moisture retention, EC behavior, and dryback rates.
"""

import os
import json
import logging
from typing import Optional, Dict

_LOGGER = logging.getLogger(__name__)

# Define characteristic profiles for common media types.
# Values are on a 0.0 to 1.0 scale:
#   retention: relative water-holding capacity (higher = holds more moisture, slower to dry)
#   dryback: relative drying speed (higher = dries out faster)
#   ec_buffer: relative nutrient/EC buffering capacity (higher = buffers more, slower EC changes)
MEDIA_PROFILES: Dict[str, Dict[str, float]] = {
    "Peat Moss":    {"retention": 0.9, "dryback": 0.2, "ec_buffer": 0.9},
    "Coco Coir":    {"retention": 0.8, "dryback": 0.3, "ec_buffer": 0.8},
    "Rockwool":     {"retention": 0.7, "dryback": 0.7, "ec_buffer": 0.1},
    "Perlite Blend": {"retention": 0.5, "dryback": 0.9, "ec_buffer": 0.4},
}


def infer_media_type(moisture_retention: float, ec_behavior: float, dryback_rate: float, 
                     plant_id: Optional[str] = None) -> Dict[str, float]:
    """Infer the likely growing media type from sensor pattern metrics.

    Parameters:
      - moisture_retention: Observed fraction (0-1) of moisture retained after saturation over a period 
                            (higher means the medium holds water longer).
      - ec_behavior: Observed nutrient/EC buffering indicator (0-1, higher means the medium buffers nutrients more, i.e., slower EC change).
      - dryback_rate: Observed relative drying speed (0-1, higher means faster dryback).

    If plant_id is provided, the result will be stored under that plant's entry in the JSON file.
    Returns a dictionary with 'media_type' and 'confidence' (confidence in [0,1]).
    Also writes the latest inference result to data/media_type_estimates.json.
    """
    # Validate and normalize inputs
    if any(val is None for val in (moisture_retention, ec_behavior, dryback_rate)):
        _LOGGER.error("Invalid sensor pattern inputs: %s, %s, %s", moisture_retention, ec_behavior, dryback_rate)
        return None
    try:
        moisture_retention_val = float(moisture_retention)
        ec_behavior_val = float(ec_behavior)
        dryback_rate_val = float(dryback_rate)
    except (ValueError, TypeError) as err:
        _LOGGER.error("Could not convert inputs to floats: %s", err)
        return None

    # If values appear to be percentages (greater than 1.0 but <= 100), convert to 0-1 scale
    if (moisture_retention_val > 1 or ec_behavior_val > 1 or dryback_rate_val > 1) and (
        moisture_retention_val <= 100 and ec_behavior_val <= 100 and dryback_rate_val <= 100):
        moisture_retention_val /= 100.0
        ec_behavior_val /= 100.0
        dryback_rate_val /= 100.0
        _LOGGER.info("Interpreting input values as percentages (0-100); converted to 0-1 scale.")

    # Clamp values to [0.0, 1.0]
    moisture_retention_val = max(0.0, min(1.0, moisture_retention_val))
    ec_behavior_val = max(0.0, min(1.0, ec_behavior_val))
    dryback_rate_val = max(0.0, min(1.0, dryback_rate_val))

    # Compare against each known media profile to find the best match
    best_match = None
    smallest_diff = float("inf")
    for media, profile in MEDIA_PROFILES.items():
        diff = (abs(profile["retention"] - moisture_retention_val) +
                abs(profile["dryback"] - dryback_rate_val) +
                abs(profile["ec_buffer"] - ec_behavior_val))
        if diff < smallest_diff:
            smallest_diff = diff
            best_match = media

    # Calculate a confidence score (1.0 means perfect match, 0.0 means very different from known profiles)
    max_diff = 3.0  # maximum possible diff (if each of the three metrics differ by 1.0)
    confidence = max(0.0, 1.0 - (smallest_diff / max_diff))
    confidence = round(confidence, 3)

    result_data = {"media_type": best_match, "confidence": confidence}

    # Prepare to save result to file
    output_path = os.path.join("data", "media_type_estimates.json")
    if plant_id:
        # Store results in a dictionary per plant
        try:
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8") as f:
                    all_results = json.load(f)
            else:
                all_results = {}
        except Exception as err:
            _LOGGER.error("Could not read media_type_estimates.json: %s. Starting fresh.", err)
            all_results = {}
        if not isinstance(all_results, dict):
            # If file was not in expected format, reset to empty dict
            all_results = {}
        all_results[str(plant_id)] = result_data
        data_to_write = all_results
    else:
        # No plant_id given, store only the single latest result (overwriting any existing file)
        data_to_write = result_data

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data_to_write, f, indent=2)
    except Exception as err:
        _LOGGER.error("Failed to write media type estimate to %s: %s", output_path, err)

    _LOGGER.info("Media type inference result: %s with confidence %.3f", best_match, confidence)
    return result_data
