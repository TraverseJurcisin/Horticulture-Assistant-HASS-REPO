import pytest

from plant_engine import ph_manager


def test_get_ph_range():
    rng = ph_manager.get_ph_range("citrus")
    assert rng == [5.5, 6.5]
    lettuce = ph_manager.get_ph_range("lettuce")
    assert lettuce == [5.8, 6.2]


def test_recommend_ph_adjustment():
    assert ph_manager.recommend_ph_adjustment(5.0, "citrus") == "increase"
    assert ph_manager.recommend_ph_adjustment(7.0, "citrus") == "decrease"
    assert ph_manager.recommend_ph_adjustment(6.0, "citrus") is None


def test_recommend_unknown_or_invalid():
    assert ph_manager.get_ph_range("unknown") == []
    assert ph_manager.recommend_ph_adjustment(6.0, "unknown") is None
    with pytest.raises(ValueError):
        ph_manager.recommend_ph_adjustment(-1, "citrus")


def test_recommended_ph_setpoint():
    assert ph_manager.recommended_ph_setpoint("citrus") == 6.0
    assert ph_manager.recommended_ph_setpoint("unknown") is None


def test_estimate_ph_adjustment_volume():
    # 10 L solution from pH 7.0 to 6.0 using acid with -0.1 per ml/L
    ml = ph_manager.estimate_ph_adjustment_volume(7.0, 6.0, 10, "ph_down")
    assert ml == 100.0

    # Unknown product returns None
    assert ph_manager.estimate_ph_adjustment_volume(6.0, 6.5, 5, "foo") is None

    # Zero delta requires no adjustment
    assert ph_manager.estimate_ph_adjustment_volume(6.5, 6.5, 5, "ph_up") == 0.0

    with pytest.raises(ValueError):
        ph_manager.estimate_ph_adjustment_volume(6.0, 6.5, 0, "ph_up")

