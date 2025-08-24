from plant_engine.light_spectrum import (
    get_red_blue_ratio,
    get_spectrum,
    list_supported_plants,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants
    assert "citrus" in plants


def test_get_spectrum():
    spec = get_spectrum("lettuce", "seedling")
    assert spec == {"red": 0.4, "blue": 0.6}


def test_get_red_blue_ratio():
    ratio = get_red_blue_ratio("lettuce", "seedling")
    assert ratio == 0.67
