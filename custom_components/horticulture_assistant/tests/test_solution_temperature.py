from plant_engine.solution_temperature import (
    list_supported_plants,
    get_temperature_range,
    evaluate_solution_temperature,
    recommend_temperature_adjustment,
)


def test_get_temperature_range():
    assert get_temperature_range("lettuce") == (16.0, 20.0)
    assert get_temperature_range("unknown") == (18.0, 22.0)


def test_evaluate_solution_temperature():
    assert evaluate_solution_temperature(15, "lettuce") == "low"
    assert evaluate_solution_temperature(25, "lettuce") == "high"
    assert evaluate_solution_temperature(18, "lettuce") is None


def test_recommend_temperature_adjustment():
    assert recommend_temperature_adjustment(15, "tomato") == "heat"
    assert recommend_temperature_adjustment(25, "tomato") == "cool"
    assert recommend_temperature_adjustment(22, "tomato") is None


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants and "tomato" in plants
