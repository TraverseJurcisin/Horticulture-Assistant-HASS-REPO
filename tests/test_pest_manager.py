from plant_engine.pest_manager import get_pest_guidelines, recommend_treatments


def test_get_pest_guidelines():
    guide = get_pest_guidelines("citrus")
    assert "aphids" in guide
    assert guide["scale"].startswith("Use horticultural oil")


def test_recommend_treatments():
    actions = recommend_treatments("citrus", ["aphids", "unknown"])
    assert actions["aphids"].startswith("Apply insecticidal soap")
    assert actions["unknown"] == "No guideline available"
