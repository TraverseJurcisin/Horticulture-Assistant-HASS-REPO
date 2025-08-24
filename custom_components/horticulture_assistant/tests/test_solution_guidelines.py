from plant_engine.solution_guidelines import (
    evaluate_solution,
    get_solution_guidelines,
    list_supported_plants,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants
    assert "tomato" in plants


def test_get_solution_guidelines():
    guide = get_solution_guidelines("lettuce", "vegetative")
    assert guide.ec == (1.0, 1.4)
    assert guide.ph == (5.8, 6.2)


def test_evaluate_solution():
    readings = {"ec": 1.2, "ph": 5.9, "temp_c": 17, "do_mg_l": 8}
    status = evaluate_solution(readings, "lettuce", "vegetative")
    assert status == {}
    readings["ec"] = 0.8
    status = evaluate_solution(readings, "lettuce", "vegetative")
    assert status["ec"] == "low"
