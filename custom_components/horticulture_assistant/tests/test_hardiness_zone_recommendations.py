from ..engine.plant_engine.hardiness_zone import get_hardiness_range, is_plant_suitable_for_zone, plants_for_zone


def test_get_hardiness_range():
    assert get_hardiness_range("citrus") == ("9", "11")
    assert get_hardiness_range("unknown") is None


def test_is_plant_suitable_for_zone():
    assert is_plant_suitable_for_zone("citrus", "10")
    assert not is_plant_suitable_for_zone("citrus", "5")


def test_plants_for_zone():
    plants = plants_for_zone("5")
    assert "tomato" in plants
    assert "citrus" not in plants
