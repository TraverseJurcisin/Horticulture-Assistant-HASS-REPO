from plant_engine.nutrient_mobilization import (
    get_mobilization_factor,
    apply_mobilization,
)


def test_get_mobilization_factor_default():
    assert get_mobilization_factor("N") == 0.8


def test_apply_mobilization():
    sched = {"N": 10.0, "Ca": 5.0}
    adjusted = apply_mobilization(sched)
    assert adjusted["N"] == 12.5  # 10 / 0.8
    assert adjusted["Ca"] == 10.0  # 5 / 0.5
