from plant_engine.root_temperature import get_uptake_factor, adjust_uptake
from plant_engine.nutrient_manager import get_temperature_adjusted_levels


def test_get_uptake_factor_basic():
    assert get_uptake_factor(21) == 1.0
    assert get_uptake_factor(15) == 0.7
    assert 0.89 < get_uptake_factor(19) < 0.91


def test_adjust_uptake():
    uptake = {"N": 100, "P": 50}
    adjusted = adjust_uptake(uptake, 15)
    assert adjusted == {"N": 70.0, "P": 35.0}


def test_temperature_adjusted_levels():
    levels = get_temperature_adjusted_levels("lettuce", "seedling", 15)
    assert levels["N"] == 56.0  # 80 * 0.7

