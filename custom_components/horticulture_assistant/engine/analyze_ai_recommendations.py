import openai
import os
import json
import logging
from datetime import datetime

from ..utils.json_io import load_json, save_json
from plant_engine.utils import get_pending_dir

_LOGGER = logging.getLogger(__name__)

def analyze_ai_recommendations(plant_id: str, report_path: str) -> None:
    """
    Analyze a daily report for a plant and get AI recommendations for threshold adjustments.
    Outputs a file with proposed threshold changes marked as pending.
    """
    # Read the daily report JSON
    try:
        report = load_json(report_path)
    except FileNotFoundError:
        _LOGGER.error("Report file not found: %s", report_path)
        return
    except Exception as e:
        _LOGGER.error("Failed to parse JSON report for plant %s: %s", plant_id, e)
        return
    
    # Extract relevant context from report
    thresholds = report.get("thresholds") or report.get("nutrient_thresholds") or {}
    stage = report.get("lifecycle_stage", "unknown")
    yield_val = report.get("yield")
    # Sensor data (keys may not exist if sensor readings unavailable)
    moisture = report.get("moisture")
    ec = report.get("ec")
    temperature = report.get("temperature")
    humidity = report.get("humidity")
    light = report.get("light")
    
    # Construct context for prompt
    context_lines = [f"Plant lifecycle stage: {stage}."]
    if yield_val is not None:
        context_lines.append(f"Last recorded yield: {yield_val} grams.")
    # List current thresholds
    context_lines.append("Current thresholds:")
    if thresholds:
        for key, val in thresholds.items():
            context_lines.append(f" - {key}: {val}")
    else:
        context_lines.append(" - (none)")
    # List latest sensor readings
    sensor_lines = []
    if moisture is not None:
        try:
            moisture_val = float(moisture)
        except Exception:
            moisture_val = moisture
        sensor_lines.append(f"Moisture: {round(moisture_val, 1)}%" if isinstance(moisture_val, (int, float)) else f"Moisture: {moisture_val}")
    if ec is not None:
        try:
            ec_val = float(ec)
        except Exception:
            ec_val = ec
        sensor_lines.append(f"EC: {round(ec_val, 2)} mS/cm" if isinstance(ec_val, (int, float)) else f"EC: {ec_val}")
    if temperature is not None:
        try:
            temp_val = float(temperature)
        except Exception:
            temp_val = temperature
        sensor_lines.append(f"Temperature: {round(temp_val, 1)}°C" if isinstance(temp_val, (int, float)) else f"Temperature: {temperature}")
    if humidity is not None:
        try:
            hum_val = float(humidity)
        except Exception:
            hum_val = humidity
        if isinstance(hum_val, (int, float)):
            sensor_lines.append(f"Humidity: {int(round(hum_val))}%")
        else:
            sensor_lines.append(f"Humidity: {humidity}")
    if light is not None:
        try:
            light_val = float(light)
        except Exception:
            light_val = light
        sensor_lines.append(f"Light: {int(round(light_val))} lux" if isinstance(light_val, (int, float)) else f"Light: {light}")
    if sensor_lines:
        context_lines.append("Latest sensor readings:")
        for line in sensor_lines:
            context_lines.append(f" - {line}")
    else:
        context_lines.append("Latest sensor readings: (unavailable)")
    
    context_str = "\n".join(context_lines)
    prompt = (
        f"{context_str}\n\n"
        "Based on this data, suggest any adjustments to the threshold values to optimize the plant's growth. "
        "Provide the new threshold values for parameters that should be updated in a JSON format.\n"
        "Output only a JSON object with the thresholds that should be updated and their recommended new values. "
        "If no changes are needed, output an empty JSON object {}. "
        "Do not include explanations or any additional text."
    )
    
    # Ensure OpenAI API key is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        _LOGGER.error("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        return
    openai.api_key = api_key
    model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    
    # Query the AI model for recommendations
    try:
        response = openai.ChatCompletion.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
    except Exception as e:
        _LOGGER.error("Failed to get AI recommendation for plant %s: %s", plant_id, e)
        return
    
    # Extract the AI's message content
    try:
        ai_message = response["choices"][0]["message"]["content"]
    except Exception as e:
        _LOGGER.error("Unexpected AI response format for plant %s: %s", plant_id, e)
        return
    
    # Parse the AI output as JSON
    try:
        suggested_thresholds = json.loads(ai_message.strip())
    except json.JSONDecodeError:
        _LOGGER.warning("AI did not return valid JSON for plant %s (output was: %r); skipping.", plant_id, ai_message)
        return
    if not isinstance(suggested_thresholds, dict):
        _LOGGER.warning("AI response for plant %s is not a JSON object (got %s); skipping.", plant_id, type(suggested_thresholds).__name__)
        return
    
    # Compare suggested thresholds with current thresholds
    old = thresholds
    new = suggested_thresholds
    changes = {}
    for k, new_val in new.items():
        old_val = old.get(k)
        if k not in old or old_val != new_val:
            changes[k] = {
                "previous_value": old_val,
                "proposed_value": new_val,
                "status": "pending"
            }
    if not changes:
        _LOGGER.info("No threshold changes recommended by AI for plant %s.", plant_id)
        return
    
    # Prepare record for pending threshold changes
    record = {
        "plant_id": plant_id,
        "timestamp": datetime.now().isoformat(),
        "original_thresholds": old,
        "proposed_thresholds": new,
        "changes": changes
    }
    
    # Write record to data/pending_thresholds/{plant_id}_{YYYY-MM-DD}.json
    base_dir = get_pending_dir()
    os.makedirs(base_dir, exist_ok=True)
    date_str = datetime.now().date().isoformat()
    ts = report.get("timestamp")
    if ts:
        try:
            date_str = datetime.fromisoformat(ts).date().isoformat()
        except Exception:
            pass
    filename = f"{plant_id}_{date_str}.json"
    file_path = os.path.join(str(base_dir), filename)
    try:
        save_json(file_path, record)
    except Exception as e:
        _LOGGER.error("Failed to save pending thresholds for plant %s: %s", plant_id, e)
        return
    
    _LOGGER.info("Queued %d threshold change(s) for plant %s (saved to %s)", len(changes), plant_id, file_path)
    for k, info in changes.items():
        _LOGGER.info("Plant %s: suggested change - %s: %s -> %s", plant_id, k, info.get("previous_value"), info.get("proposed_value"))
