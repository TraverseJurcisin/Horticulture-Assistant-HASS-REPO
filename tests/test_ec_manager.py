import pytest

from plant_engine import ec_manager


def test_get_ec_range():
    rng = ec_manager.get_ec_range("citrus", "seedling")
    assert rng == [1.0, 1.2]
    assert ec_manager.get_ec_range("unknown") == []


def test_recommend_ec_adjustment():
    assert ec_manager.recommend_ec_adjustment(0.8, "citrus", "seedling") == "increase"
    assert ec_manager.recommend_ec_adjustment(1.3, "citrus", "seedling") == "decrease"
    assert ec_manager.recommend_ec_adjustment(1.1, "citrus", "seedling") is None
    with pytest.raises(ValueError):
        ec_manager.recommend_ec_adjustment(-1, "citrus")


def test_recommended_ec_setpoint():
    assert ec_manager.recommended_ec_setpoint("citrus", "seedling") == 1.1
    assert ec_manager.recommended_ec_setpoint("unknown") is None

