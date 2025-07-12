import os
import json
import openai  # Optional, only if using OpenAI's API
from typing import Dict

# === Configuration ===

USE_OPENAI = False  # Toggle between mock mode and API
OPENAI_MODEL = "gpt-4o"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)  # Stored in environment variable

# === Mock model ===

def mock_adjust_thresholds(data: Dict) -> Dict:
    """Offline fallback / placeholder model."""
    old_thresholds = data.get("thresholds", {})
    lifecycle = data.get("lifecycle_stage", "")
    adjusted = {}

    for k, v in old_thresholds.items():
        if "leaf_" in k:
            if lifecycle == "fruiting":
                adjusted[k] = round(v * 1.05, 2)
            elif lifecycle == "vegetative":
                adjusted[k] = round(v * 0.95, 2)
            else:
                adjusted[k] = v
        else:
            adjusted[k] = v

    return adjusted


# === OpenAI API wrapper ===

def openai_adjust_thresholds(data: Dict) -> Dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set in environment.")

    openai.api_key = OPENAI_API_KEY

    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert horticulturist AI. "
                    "You receive plant data including nutrient thresholds, lifecycle stage, and sensor data. "
                    "Return a dictionary of updated nutrient thresholds based on optimal plant performance."
                )
            },
            {
                "role": "user",
                "content": f"Input data:\n{json.dumps(data, indent=2)}"
            }
        ],
        temperature=0.3,
    )

    text = response["choices"][0]["message"]["content"]

    try:
        updated = json.loads(text)
        return updated
    except json.JSONDecodeError:
        raise ValueError("OpenAI returned non-JSON output:\n" + text)


# === Public Interface ===

def analyze(data: Dict) -> Dict:
    """
    Perform AI analysis and return updated thresholds.
    This is the single interface other code should use.
    """
    if USE_OPENAI:
        return openai_adjust_thresholds(data)
    else:
        return mock_adjust_thresholds(data)
