from plant_engine.growth_stage import get_stage_image


def test_get_stage_image_known():
    url = get_stage_image("tomato", "seedling")
    assert url.startswith("https://")


def test_get_stage_image_unknown():
    assert get_stage_image("unknown", "seedling") is None
