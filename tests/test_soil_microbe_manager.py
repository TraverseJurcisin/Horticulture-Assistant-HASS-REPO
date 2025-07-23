from plant_engine import soil_microbe_manager as sm


def test_list_supported_plants():
    plants = sm.list_supported_plants()
    assert "citrus" in plants
    assert "tomato" in plants


def test_get_recommended_microbes():
    microbes = sm.get_recommended_microbes("lettuce")
    assert "Azotobacter chroococcum" in microbes
    assert len(microbes) == 2
