import asyncio
import json
import os
import logging
from datetime import datetime

from ..utils.ai_async import async_chat_completion

_LOGGER = logging.getLogger(__name__)

def _generate_mock_reply(thresholds: dict) -> dict:
    """
    Generate a mock AI reply by adjusting some threshold values by +5%.
    Returns a dict of proposed new threshold values (subset of the input).
    """
    if not thresholds:
        return {}
    # Determine how many thresholds to adjust (up to 3)
    keys = list(thresholds.keys())
    num_to_adjust = min(len(keys), 3)
    proposed = {}
    count = 0
    for key in keys:
        if count >= num_to_adjust:
            break
        value = thresholds.get(key)
        # Only adjust numeric values or lists of numerics
        if isinstance(value, (int, float)):
            new_val = value * 1.05
            # Round values: integers back to int, floats to 2 decimal places
            if isinstance(value, int):
                new_val = int(round(new_val))
            else:
                new_val = round(new_val, 2)
            proposed[key] = new_val
            count += 1
        elif isinstance(value, list):
            # Check if list consists purely of numbers
            new_list = []
            all_numbers = True
            for elem in value:
                if isinstance(elem, (int, float)):
                    new_elem = elem * 1.05
                    if isinstance(elem, int):
                        new_elem = int(round(new_elem))
                    else:
                        new_elem = round(new_elem, 2)
                    new_list.append(new_elem)
                else:
                    all_numbers = False
                    break
            if all_numbers:
                proposed[key] = new_list
                count += 1
        # Non-numeric types are not adjusted (skipped)
    return proposed

def dispatch_ai_context(context_dict: dict, plant_id: str, base_path: str,
                        use_openai: bool = True, log: bool = True) -> dict:
    """
    Send context data to an AI model (OpenAI or mock) to get improved threshold suggestions.
    Saves the input context and AI response to files under base_path/ai_feedback.
    Returns a dict with plant_id, proposed_thresholds, raw AI output, source, and timestamp.
    """
    # Ensure ai_feedback directory exists
    ai_dir = os.path.join(base_path, "ai_feedback")
    os.makedirs(ai_dir, exist_ok=True)
    # Determine date string for filenames (use context timestamp if available)
    date_str = datetime.now().date().isoformat()
    context_ts = context_dict.get("timestamp")
    if context_ts:
        try:
            date_str = datetime.fromisoformat(str(context_ts)).date().isoformat()
        except Exception:
            # If context timestamp is not parseable, use current date
            pass
    # Save the context_dict to a JSON file
    context_filename = f"{plant_id}_{date_str}.json"
    context_path = os.path.join(ai_dir, context_filename)
    try:
        with open(context_path, "w", encoding="utf-8") as f:
            json.dump(context_dict, f, indent=2)
        if log:
            _LOGGER.info("Context saved for plant %s at %s", plant_id, context_path)
    except Exception as e:
        if log:
            _LOGGER.error("Failed to save context for plant %s: %s", plant_id, e)
    # Prepare variables for result
    proposed_thresholds = {}
    ai_raw_response = ""
    source = "openai" if use_openai else "mock"
    # Call OpenAI API or use mock response
    if use_openai:
        # Ensure API key is set
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            _LOGGER.error("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
            ai_raw_response = "OpenAI API key not found"
        else:
            model_name = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
            try:
                response = asyncio.run(
                    async_chat_completion(
                        api_key,
                        model_name,
                        [
                            {
                                "role": "system",
                                "content": (
                                    "You are a horticulture AI assistant optimizing plant yield and health. "
                                    "Return improved threshold values based on data."
                                ),
                            },
                            {"role": "user", "content": json.dumps(context_dict)},
                        ],
                        timeout=30,
                    )
                )
            except Exception as e:
                _LOGGER.error("OpenAI API call failed for plant %s: %s", plant_id, e)
                ai_raw_response = f"OpenAI API call error: {e}"
            else:
                # Extract the AI's response message content
                try:
                    ai_raw_response = response["choices"][0]["message"]["content"]
                except Exception as e:
                    _LOGGER.error("Unexpected OpenAI response format for plant %s: %s", plant_id, e)
                    ai_raw_response = ""
                # Parse AI response if possible
                if ai_raw_response:
                    try:
                        parsed = json.loads(ai_raw_response.strip())
                    except json.JSONDecodeError:
                        _LOGGER.warning("AI did not return valid JSON for plant %s (output was: %r)", plant_id, ai_raw_response)
                    else:
                        if isinstance(parsed, dict):
                            proposed_thresholds = parsed
                        else:
                            _LOGGER.warning(
                                "AI response for plant %s is not a JSON object (got %s)",
                                plant_id,
                                type(parsed).__name__,
                            )
    else:
        # Use offline mock model to generate threshold suggestions
        thresholds = context_dict.get("thresholds") or context_dict.get("nutrient_thresholds") or {}
        proposed_thresholds = _generate_mock_reply(thresholds)
        # Create a brief raw description of the mock changes
        if proposed_thresholds:
            ai_raw_response = f"Mock adjusted {len(proposed_thresholds)} thresholds by +5%"
        else:
            ai_raw_response = "Mock did not adjust any thresholds"
    # Compile the result dictionary
    result = {
        "plant_id": plant_id,
        "proposed_thresholds": proposed_thresholds,
        "ai_raw": ai_raw_response,
        "source": source,
        "timestamp": datetime.now().isoformat()
    }
    # Save the AI response to a JSON file
    response_filename = f"response_{plant_id}_{date_str}.json"
    response_path = os.path.join(ai_dir, response_filename)
    try:
        with open(response_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        if log:
            _LOGGER.info("AI response saved for plant %s at %s", plant_id, response_path)
    except Exception as e:
        if log:
            _LOGGER.error("Failed to save AI response for plant %s: %s", plant_id, e)
    return result
