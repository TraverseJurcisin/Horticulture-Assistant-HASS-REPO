from plant_engine.pest_manager import (
    get_pest_guidelines,
    recommend_treatments,
    get_beneficial_insects,
    recommend_beneficials,
)


def test_get_pest_guidelines():
    guide = get_pest_guidelines("citrus")
    assert "aphids" in guide
    assert guide["scale"].startswith("Use horticultural oil")


def test_recommend_treatments():
    actions = recommend_treatments("citrus", ["aphids", "unknown"])
    assert actions["aphids"].startswith("Apply insecticidal soap")
    assert actions["unknown"] == "No guideline available"


def test_get_beneficial_insects():
    insects = get_beneficial_insects("aphids")
    assert "ladybugs" in insects
    assert get_beneficial_insects("unknown") == []


def test_recommend_beneficials():
    rec = recommend_beneficials(["aphids", "scale"])
    assert "ladybugs" in rec["aphids"]
    assert "parasitic wasps" in rec["scale"]
