from custom_components.horticulture_assistant.utils.nutrient_schedule import (
    generate_nutrient_schedule,
)


def test_generate_nutrient_schedule():
    schedule = generate_nutrient_schedule("citrus")
    assert schedule
    first = schedule[0]
    assert first.stage == "seedling"
    assert first.duration_days == 60
    assert abs(first.totals["N"] - 75 * 60) < 0.01


def test_generate_nutrient_schedule_cached():
    first_call = generate_nutrient_schedule("citrus")
    second_call = generate_nutrient_schedule("citrus")
    assert first_call is second_call
