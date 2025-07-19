from plant_engine.pest_manager import get_pest_guidelines


def test_get_pest_guidelines():
    guide = get_pest_guidelines("citrus")
    assert "aphids" in guide
    assert guide["scale"].startswith("Use horticultural oil")
