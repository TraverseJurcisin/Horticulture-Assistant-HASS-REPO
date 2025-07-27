from datetime import date

from plant_engine.stage_tasks import (
    get_stage_tasks,
    list_supported_plants,
    generate_task_schedule,
    generate_cycle_task_plan,
)


def test_get_stage_tasks():
    tasks = get_stage_tasks("tomato", "seedling")
    assert "Transplant seedlings to larger pots" in tasks
    assert get_stage_tasks("unknown", "seedling") == []


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "lettuce" in plants


def test_generate_task_schedule():
    schedule = generate_task_schedule(
        "tomato", "vegetative", date(2025, 1, 1), days=15, interval=7
    )
    assert len(schedule) == 3
    assert schedule[0].tasks
    assert schedule[0].date == date(2025, 1, 1)


def test_generate_cycle_task_plan():
    plan = generate_cycle_task_plan("tomato", date(2025, 1, 1))
    assert len(plan) == 19
    assert plan[0].date == date(2025, 1, 1)
