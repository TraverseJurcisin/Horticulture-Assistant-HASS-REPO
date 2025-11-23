from ..engine.plant_engine.plant_density import get_spacing_cm, list_supported_plants, plants_per_area


def test_get_spacing_cm():
    assert get_spacing_cm("lettuce") == 25
    assert get_spacing_cm("unknown") is None


def test_plants_per_area():
    assert plants_per_area("lettuce", 1.0) == round(1.0 / (0.25**2), 1)
    assert plants_per_area("citrus", 9.0) == round(9.0 / (1.5**2), 1)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants and "basil" in plants
