from plant_engine.stage_factors import get_stage_factor, list_stages


def test_get_stage_factor():
    assert get_stage_factor("fruiting") == 1.1
    assert get_stage_factor("unknown") == 1.0


def test_list_stages():
    stages = list_stages()
    assert "vegetative" in stages
