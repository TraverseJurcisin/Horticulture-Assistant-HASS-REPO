from datetime import date
from plant_engine.environment_manager import generate_cycle_growth_plan


def test_generate_cycle_growth_plan_tomato():
    start = date(2025, 1, 1)
    plan = generate_cycle_growth_plan("tomato", start)
    assert plan[0]["stage"] == "seedling"
    assert plan[0]["start_date"] == start
    assert plan[0]["environment"]["temp_c"] == 24
    assert plan[-1]["stage"] == "fruiting"
    assert plan[-1]["end_date"] == date(2025, 5, 1)

