from plant_engine.rotation_manager import (
    get_rotation_info,
    list_supported_plants,
    recommended_rotation_years,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants


def test_get_rotation_info():
    info = get_rotation_info("tomato")
    assert info.family == "solanaceae"
    assert info.years == 3


def test_recommended_rotation_years():
    assert recommended_rotation_years("lettuce") == 2
    assert recommended_rotation_years("unknown") is None
