from plant_engine.pest_manager import (
    get_pest_guidelines,
    recommend_treatments,
    get_beneficial_insects,
    recommend_beneficials,
    get_pest_prevention,
    recommend_prevention,
    get_ipm_guidelines,
    recommend_ipm_actions,
    list_known_pests,
    build_pest_management_plan,
    get_organic_control,
    recommend_organic_controls,
)


def test_get_pest_guidelines():
    guide = get_pest_guidelines("citrus")
    assert "aphids" in guide
    assert guide["scale"].startswith("Use horticultural oil")


def test_get_pest_guidelines_case_insensitive():
    guide = get_pest_guidelines("CiTrUs")
    assert "aphids" in guide


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


def test_get_organic_control():
    assert "neem" in get_organic_control("aphids").lower()
    assert get_organic_control("unknown") == ""


def test_recommend_organic_controls():
    rec = recommend_organic_controls(["aphids", "scale"])
    assert "neem" in rec["aphids"].lower()
    assert "oil" in rec["scale"].lower()


def test_list_known_pests():
    pests = list_known_pests("citrus")
    assert "aphids" in pests


def test_get_pest_prevention():
    guide = get_pest_prevention("citrus")
    assert "aphids" in guide
    assert guide["scale"].startswith("Inspect")


def test_recommend_prevention():
    rec = recommend_prevention("citrus", ["aphids", "unknown"])
    assert rec["aphids"].startswith("Encourage")
    assert rec["unknown"] == "No guideline available"


def test_get_ipm_guidelines():
    data = get_ipm_guidelines("citrus")
    assert data["general"].startswith("Prune")
    assert "aphids" in data


def test_recommend_ipm_actions():
    actions = recommend_ipm_actions("citrus", ["aphids"])
    assert "general" in actions
    assert actions["aphids"].startswith("Introduce ladybugs")


def test_build_pest_management_plan():
    plan = build_pest_management_plan("citrus", ["aphids", "unknown"])
    assert "general" in plan
    assert plan["aphids"]["treatment"].startswith("Apply insecticidal")
    assert "ladybugs" in plan["aphids"]["beneficials"]
    assert "neem" in plan["aphids"]["organic"].lower()
    assert plan["unknown"]["treatment"] == "No guideline available"
