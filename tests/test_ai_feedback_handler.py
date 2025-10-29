from __future__ import annotations

import importlib
import json
from pathlib import Path


def _write_profile(path: Path, moisture: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"thresholds": {"moisture": moisture}}), encoding="utf-8")


def test_process_ai_feedback_sanitises_profile_path(tmp_path, monkeypatch):
    """Auto-approved feedback must not allow directory traversal when saving."""

    monkeypatch.chdir(tmp_path)

    const_module = importlib.import_module("custom_components.horticulture_assistant.const")
    const_module.CONF_USE_OPENAI = "use_openai"
    const_module.CONF_OPENAI_MODEL = "openai_model"
    const_module.CONF_OPENAI_API_KEY = "openai_api_key"
    const_module.CONF_OPENAI_TEMPERATURE = "openai_temperature"

    ai_feedback_handler = importlib.reload(
        importlib.import_module("custom_components.horticulture_assistant.utils.ai_feedback_handler")
    )

    monkeypatch.setattr(
        ai_feedback_handler.global_config,
        "load_config",
        lambda: {
            ai_feedback_handler.CONF_USE_OPENAI: False,
            ai_feedback_handler.CONF_OPENAI_MODEL: "gpt-4o",
            ai_feedback_handler.CONF_OPENAI_API_KEY: "",
            ai_feedback_handler.CONF_OPENAI_TEMPERATURE: 0.3,
        },
    )
    monkeypatch.setattr(
        ai_feedback_handler.ai_model,
        "analyze",
        lambda report, cfg: {"thresholds": {"moisture": 55}, "advice": "Update applied"},
    )

    unsafe_path = tmp_path / "escape.json"
    safe_path = tmp_path / "plants" / "escape.json"
    _write_profile(unsafe_path, 40)
    _write_profile(safe_path, 40)

    report = {
        "plant_id": "../escape",
        "thresholds": {"moisture": 40},
        "ai_feedback_required": False,
    }

    advice = ai_feedback_handler.process_ai_feedback("../escape", report)

    assert advice == "Update applied"
    assert json.loads(unsafe_path.read_text(encoding="utf-8"))["thresholds"]["moisture"] == 40
    assert json.loads(safe_path.read_text(encoding="utf-8"))["thresholds"]["moisture"] == 55
