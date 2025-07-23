from plant_engine.canopy_manager import list_supported_plants, get_default_canopy_area


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert isinstance(plants, list)


def test_get_default_canopy_area():
    assert get_default_canopy_area("tomato") == 0.3
    # Unknown plant returns default
    assert get_default_canopy_area("unknown") == 0.25
