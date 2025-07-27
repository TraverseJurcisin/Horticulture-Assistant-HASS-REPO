from plant_engine import ai_model


def test_get_model_defaults_to_mock():
    model = ai_model.get_model()
    assert isinstance(model, ai_model.MockAIModel)


def test_analyze_uses_mock_model():
    data = {"thresholds": {"leaf_temp": 20}, "lifecycle_stage": "vegetative"}
    updated = ai_model.analyze(data)
    assert updated["leaf_temp"] == 19.0


def test_get_model_openai():
    cfg = ai_model.AIModelConfig(use_openai=True, api_key="key")
    model = ai_model.get_model(cfg)
    assert isinstance(model, ai_model.OpenAIModel)
