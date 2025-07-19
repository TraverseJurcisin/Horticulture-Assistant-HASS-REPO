from plant_engine.nutrient_manager import get_recommended_levels


def test_get_recommended_levels():
    levels = get_recommended_levels("citrus", "fruiting")
    assert levels["N"] == 120
    assert levels["K"] == 100
