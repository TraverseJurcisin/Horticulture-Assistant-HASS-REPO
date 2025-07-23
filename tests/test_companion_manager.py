from plant_engine import companion_manager


def test_list_supported_plants():
    plants = companion_manager.list_supported_plants()
    assert "tomato" in plants
    assert "lettuce" in plants


def test_get_companion_guidelines():
    guide = companion_manager.get_companion_guidelines("tomato")
    assert "basil" in guide.get("companions", [])
    assert "cabbage" in guide.get("antagonists", [])


def test_list_companions_antagonists():
    comps = companion_manager.list_companions("cucumber")
    ants = companion_manager.list_antagonists("cucumber")
    assert "dill" in comps
    assert "sage" in ants
