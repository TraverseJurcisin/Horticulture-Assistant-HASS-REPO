from plant_engine.soil_manager import (
    list_supported_plants,
    get_soil_targets,
    calculate_soil_deficiencies,
    calculate_soil_surplus,
    score_soil_nutrients,
    calculate_soil_balance,
    recommend_soil_amendments,
)


def test_get_soil_targets():
    targets = get_soil_targets("citrus")
    assert targets == {"N": 80.0, "P": 30.0, "K": 90.0}


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "citrus" in plants


def test_calculate_soil_deficiencies():
    diffs = calculate_soil_deficiencies({"N": 50, "P": 20, "K": 60}, "citrus")
    assert diffs["N"] == 30
    assert diffs["P"] == 10
    assert diffs["K"] == 30


def test_calculate_soil_surplus():
    surp = calculate_soil_surplus({"N": 90, "P": 35, "K": 100}, "citrus")
    assert surp["N"] == 10
    assert surp["P"] == 5
    assert surp["K"] == 10


def test_score_soil_nutrients():
    good = score_soil_nutrients({"N": 80, "P": 30, "K": 90}, "citrus")
    poor = score_soil_nutrients({"N": 20, "P": 5, "K": 20}, "citrus")
    assert good > poor
    assert good >= 90


def test_calculate_soil_balance():
    balance = calculate_soil_balance({"N": 40, "P": 15, "K": 45}, "citrus")
    assert balance == {"N": 0.5, "P": 0.5, "K": 0.5}

def test_recommend_soil_amendments():
    rec = recommend_soil_amendments(
        {"N": 40, "P": 15, "K": 45},
        "citrus",
        1000,
        {"N": "urea", "P": "map", "K": "kcl"},
    )
    assert rec["urea"] > 0
    assert rec["map"] > 0
    assert rec["kcl"] > 0
