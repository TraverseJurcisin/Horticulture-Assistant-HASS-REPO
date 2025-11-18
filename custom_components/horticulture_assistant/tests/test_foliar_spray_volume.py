from plant_engine.fertigation import estimate_spray_solution_volume, get_foliar_spray_volume


def test_get_foliar_spray_volume():
    assert get_foliar_spray_volume("tomato", "vegetative") == 50
    assert get_foliar_spray_volume("tomato", "flowering") == 60
    assert get_foliar_spray_volume("tomato") == 55
    assert get_foliar_spray_volume("unknown") is None


def test_estimate_spray_solution_volume():
    vol = estimate_spray_solution_volume(10, "tomato", "vegetative")
    assert vol == 0.5
    assert estimate_spray_solution_volume(5, "lettuce") == 0.15
    assert estimate_spray_solution_volume(3, "unknown") is None
