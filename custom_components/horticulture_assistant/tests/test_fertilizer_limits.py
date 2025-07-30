from plant_engine import fertilizer_limits
import pytest


def test_get_limit_known():
    assert fertilizer_limits.get_limit("foxfarm_grow_big") == 150
    assert fertilizer_limits.get_limit("general_hydroponics_floramicro") == 120
    assert fertilizer_limits.get_limit("unknown") is None


def test_check_schedule():
    schedule = {
        "foxfarm_grow_big": 200,
        "general_hydroponics_florabloom": 60,
    }
    warnings = fertilizer_limits.check_schedule(schedule, 1)
    assert warnings["foxfarm_grow_big"] > 0
    assert "general_hydroponics_florabloom" not in warnings

    with pytest.raises(ValueError):
        fertilizer_limits.check_schedule(schedule, 0)
