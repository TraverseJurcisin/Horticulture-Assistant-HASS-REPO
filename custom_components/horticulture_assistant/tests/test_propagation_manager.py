from ..engine.plant_engine.propagation_manager import (
    get_propagation_guidelines,
    list_propagation_methods,
    list_supported_plants,
    propagation_success_score,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "lettuce" in plants


def test_get_propagation_guidelines():
    guide = get_propagation_guidelines("tomato", "seed")
    assert guide["temperature_c"] == [21, 27]


def test_list_propagation_methods():
    methods = list_propagation_methods("tomato")
    assert "seed" in methods
    assert "cutting" in methods


def test_propagation_success_score():
    env = {"temperature_c": 24, "humidity_pct": 80}
    score = propagation_success_score(env, "tomato", "seed")
    assert 0 < score <= 100
