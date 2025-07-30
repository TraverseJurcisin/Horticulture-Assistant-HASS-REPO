from plant_engine.disease_manager import get_disease_prevention, recommend_prevention


def test_get_disease_prevention():
    guide = get_disease_prevention("citrus")
    assert "root rot" in guide
    assert guide["citrus greening"].startswith("Use disease-free")


def test_recommend_prevention():
    actions = recommend_prevention("citrus", ["root rot", "unknown"])
    assert actions["root rot"].startswith("Plant in well-drained")
    assert actions["unknown"] == "No guideline available"
