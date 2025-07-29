from plant_engine.root_temperature import (
    get_uptake_factor,
    adjust_uptake,
    get_optimal_range,
    classify_soil_temperature,
)
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


def test_get_optimal_range():
    assert get_optimal_range("lettuce") == (16.0, 22.0)
    assert get_optimal_range("lettuce", "germination") == (10.0, 22.0)
    assert get_optimal_range("unknown") is None


def test_classify_soil_temperature():
    assert classify_soil_temperature(12, "lettuce") == "cold"
    assert classify_soil_temperature(18, "lettuce") == "optimal"
    assert classify_soil_temperature(25, "lettuce") == "hot"
    assert classify_soil_temperature(20, "unknown") is None

