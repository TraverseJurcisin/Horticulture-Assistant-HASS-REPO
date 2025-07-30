from plant_engine.environment_manager import (
    get_target_soil_moisture,
    evaluate_moisture_stress,
)


def test_get_target_soil_moisture():
    assert get_target_soil_moisture("citrus", "seedling") == (30, 50)
    assert get_target_soil_moisture("unknown") is None


def test_evaluate_moisture_stress():
    assert evaluate_moisture_stress(20, "citrus", "seedling") == "dry"
    assert evaluate_moisture_stress(55, "citrus", "seedling") == "wet"
    assert evaluate_moisture_stress(40, "citrus", "seedling") is None
