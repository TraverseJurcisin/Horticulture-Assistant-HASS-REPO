from ..engine.plant_engine import planting_guidelines as pg


def test_get_planting_depth():
    depth = pg.get_planting_depth("tomato")
    assert depth == 2.5


def test_list_supported_plants():
    plants = pg.list_supported_plants()
    assert "lettuce" in plants
    assert "basil" in plants
