import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def load_ai_insight_context(plant_id: str, base_path: str = "plants", analytics_path: str = "analytics"):
    """
    Load recent plant data and compile context for AI insights.
    
    Reads the plant's profile and recent growth/yield analytics to assemble a context dictionary containing:
      - plant_id: the plant identifier (string)
      - lifecycle_stage: current lifecycle stage of the plant (string)
      - current_thresholds: current threshold values from the plant profile (dict)
      - growth_trend: list of recent growth metric values (last 7 data points, most recent last)
      - yield_cumulative: latest cumulative yield value for the plant (float or int)
    
    The plant profile is expected at `{base_path}/{plant_id}.json` and growth/yield data at `{analytics_path}/{plant_id}_growth_yield.json`.
    Returns:
      A dictionary with the keys listed above, for use in downstream AI evaluation.
    """
    # Initialize context with default values
    context = {
        "plant_id": plant_id,
        "lifecycle_stage": "unknown",
        "current_thresholds": {},
        "growth_trend": [],
        "yield_cumulative": 0.0
    }
    
    # Construct file paths
    profile_path = Path(base_path) / f"{plant_id}.json"
    analytics_file = Path(analytics_path) / f"{plant_id}_growth_yield.json"
    
    # Load plant profile JSON
    profile = {}
    try:
        with open(profile_path, "r", encoding="utf-8") as pf:
            profile = json.load(pf)
    except FileNotFoundError:
        _LOGGER.error("Plant profile not found for '%s' at %s", plant_id, profile_path)
        # If profile is missing, return context with default values (plant_id already set)
        return context
    except json.JSONDecodeError as e:
        _LOGGER.error("Failed to parse profile for plant '%s': %s", plant_id, e)
        return context
    
    if not isinstance(profile, dict):
        _LOGGER.error("Profile data for plant '%s' is invalid format (expected dict)", plant_id)
        return context
    
    # Extract lifecycle stage (with fallback to nested structure if applicable)
    lifecycle_stage = profile.get("lifecycle_stage") or profile.get("general", {}).get("lifecycle_stage") \
                      or profile.get("general", {}).get("stage") or "unknown"
    context["lifecycle_stage"] = lifecycle_stage
    
    # Extract current thresholds (ensure dictionary)
    thresholds = profile.get("thresholds")
    if thresholds is None:
        thresholds = {}
    elif not isinstance(thresholds, dict):
        _LOGGER.warning("Unexpected thresholds format in profile %s; defaulting to empty dict.", plant_id)
        thresholds = {}
    context["current_thresholds"] = thresholds
    
    # Load recent growth/yield data
    series = []
    try:
        with open(analytics_file, "r", encoding="utf-8") as af:
            data = json.load(af)
        if isinstance(data, list):
            series = data
        else:
            _LOGGER.warning("Growth/yield data for plant %s is not a list; ignoring content.", plant_id)
    except FileNotFoundError:
        _LOGGER.warning("Growth/yield data file not found for plant %s at %s", plant_id, analytics_file)
    except json.JSONDecodeError as e:
        _LOGGER.error("Failed to read growth/yield data for plant '%s': %s", plant_id, e)
    except Exception as e:
        _LOGGER.error("Unexpected error loading growth/yield data for plant '%s': %s", plant_id, e)
    
    if series:
        # Determine latest cumulative yield from last entry
        last_entry = series[-1]
        if isinstance(last_entry, dict):
            context["yield_cumulative"] = last_entry.get("cumulative_yield", 0.0)
        else:
            _LOGGER.warning("Last entry in growth/yield data for plant %s is not a dict: %s", plant_id, last_entry)
            context["yield_cumulative"] = 0.0
        # Collect the last up to 7 growth metric values
        growth_entries = [entry for entry in series if isinstance(entry, dict) and entry.get("growth_metric") is not None]
        context["growth_trend"] = [entry.get("growth_metric") for entry in growth_entries[-7:]] if growth_entries else []
    else:
        # No data available, leave defaults (growth_trend empty, yield_cumulative 0.0)
        context["growth_trend"] = []
        context["yield_cumulative"] = 0.0
    
    return context
