from ..engine.plant_engine.dissolved_oxygen import (
    evaluate_dissolved_oxygen,
    get_oxygen_range,
    list_supported_plants,
    recommend_oxygen_adjustment,
)


def test_get_oxygen_range():
    assert get_oxygen_range("lettuce") == (7.0, 10.0)
    assert get_oxygen_range("unknown") == (6.0, 10.0)


def test_evaluate_dissolved_oxygen():
    assert evaluate_dissolved_oxygen(5, "lettuce") == "low"
    assert evaluate_dissolved_oxygen(11, "lettuce") == "high"
    assert evaluate_dissolved_oxygen(8, "lettuce") is None


def test_recommend_oxygen_adjustment():
    assert recommend_oxygen_adjustment(5, "tomato") == "aerate"
    assert recommend_oxygen_adjustment(11, "tomato") == "reduce_aeration"
    assert recommend_oxygen_adjustment(8, "tomato") is None


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants and "basil" in plants
