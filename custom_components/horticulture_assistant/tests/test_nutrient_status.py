from ..engine.plant_engine.nutrient_status import classify_nutrient_status


def test_classify_nutrient_status():
    current = {"N": 60, "P": 20, "K": 351, "Ca": 60}
    status = classify_nutrient_status(current, "tomato", "fruiting")
    assert status["N"] == "moderate deficiency"
    assert status["P"] == "severe deficiency"
    assert status["K"] == "excessive"
    assert status["Ca"] == "adequate"
