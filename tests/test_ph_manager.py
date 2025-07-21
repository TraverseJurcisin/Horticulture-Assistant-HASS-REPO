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

