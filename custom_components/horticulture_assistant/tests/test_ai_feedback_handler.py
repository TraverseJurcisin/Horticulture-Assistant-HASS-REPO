import json

from custom_components.horticulture_assistant.utils import ai_feedback_handler


def test_process_ai_feedback_uses_global_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    plants_dir = tmp_path / "plants"
    data_dir.mkdir()
    plants_dir.mkdir()
    cfg = {
        "use_openai": True,
        "openai_api_key": "abc",
        "openai_model": "model-x",
        "openai_temperature": 0.4,
        "default_threshold_mode": "profile",
    }
    (data_dir / "horticulture_global_config.json").write_text(json.dumps(cfg))
    (plants_dir / "plant1.json").write_text(json.dumps({"thresholds": {}, "auto_approve_all": False}))

    captured = {}

    def fake_analyze(data, config=None):
        captured["config"] = config
        return {"thresholds": {}}

    monkeypatch.setattr(ai_feedback_handler.ai_model, "analyze", fake_analyze)

    ai_feedback_handler.process_ai_feedback("plant1", {"thresholds": {}})

    model_cfg = captured["config"]
    assert model_cfg.use_openai is True
    assert model_cfg.api_key == "abc"
    assert model_cfg.model == "model-x"
    assert model_cfg.temperature == 0.4
