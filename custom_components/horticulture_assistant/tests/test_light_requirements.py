from custom_components.horticulture_assistant.utils.light_requirements import (
    get_stage_light,
    generate_light_schedule,
)


def test_get_stage_light():
    assert get_stage_light("citrus", "vegetative") == 500
    assert get_stage_light("tomato", "flowering") == 600
    assert get_stage_light("unknown", "stage") is None


def test_generate_light_schedule():
    sched = generate_light_schedule("tomato")
    assert sched["seedling"] == 200
    assert sched["fruiting"] == 650
    assert generate_light_schedule("unknown") == {}
