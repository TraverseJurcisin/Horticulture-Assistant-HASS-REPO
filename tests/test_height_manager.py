from plant_engine.height_manager import (
    list_supported_plants,
    get_height_range,
    estimate_height,
)


def test_get_height_range():
    rng = get_height_range("tomato", "vegetative")
    assert rng == (20.0, 60.0)


def test_estimate_height():
    assert estimate_height("tomato", "vegetative", 0) == 20.0
    assert estimate_height("tomato", "vegetative", 50) == 40.0
    assert estimate_height("tomato", "vegetative", 100) == 60.0


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants and "lettuce" in plants
