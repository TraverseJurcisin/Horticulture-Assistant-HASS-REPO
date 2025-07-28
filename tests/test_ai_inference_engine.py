from custom_components.horticulture_assistant.utils.ai_inference_engine import (
    AIInferenceEngine,
    DailyPackage,
)
import json


def _sample_package():
    return DailyPackage(
        date="2024-01-01",
        plant_data={
            "p1": {
                "plant_type": "tomato",
                "growth_rate": 0.5,
                "expected_growth": 1.0,
                "yield": 7.0,
                "expected_yield": 10,
                "ec": 3.0,
            }
        },
        environment_data={
            "p1": {"temp_c": 26, "humidity_pct": 80}
        },
        fertigation_data={},
    )


def test_ai_inference_engine_detects_issues():
    engine = AIInferenceEngine()
    results = engine.analyze(_sample_package())
    assert len(results) == 1
    res = results[0]
    assert "Low growth rate detected" in res.flagged_issues
    assert "Yield below expected threshold" in res.flagged_issues
    assert "High EC detected" in res.flagged_issues
    assert any("whiteflies" in issue for issue in res.flagged_issues)
    assert res.confidence < 1.0


def test_ai_inference_engine_export_results():
    engine = AIInferenceEngine()
    engine.analyze(_sample_package())
    out = engine.export_results()
    data = json.loads(out)
    assert data[0]["plant_id"] == "p1"
    engine.reset_history()
    assert engine.history == []

