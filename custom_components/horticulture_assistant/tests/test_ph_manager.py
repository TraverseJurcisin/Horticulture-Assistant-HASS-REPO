import pytest

from ..engine.plant_engine import ph_manager


def test_get_ph_range():
    rng = ph_manager.get_ph_range("citrus")
    assert rng == [5.5, 6.5]
    lettuce = ph_manager.get_ph_range("lettuce")
    assert lettuce == [5.8, 6.2]


def test_recommend_ph_adjustment():
    assert ph_manager.recommend_ph_adjustment(5.0, "citrus") == "increase"
    assert ph_manager.recommend_ph_adjustment(7.0, "citrus") == "decrease"
    assert ph_manager.recommend_ph_adjustment(6.0, "citrus") is None


def test_classify_ph():
    assert ph_manager.classify_ph(5.0, "citrus") == "low"
    assert ph_manager.classify_ph(7.0, "citrus") == "high"
    assert ph_manager.classify_ph(6.0, "citrus") == "optimal"
    assert ph_manager.classify_ph(6.0, "unknown") is None


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


def test_recommend_solution_ph_adjustment():
    ml = ph_manager.recommend_solution_ph_adjustment(7.0, "citrus", None, 10, "ph_down")
    assert ml == 100.0


def test_recommend_ph_correction():
    result = ph_manager.recommend_ph_correction(7.0, "citrus", None, 10)
    assert result == ("ph_down", 100.0)

    # No correction when within range
    assert ph_manager.recommend_ph_correction(6.0, "citrus", None, 10) is None


def test_medium_ph_functions():
    soil = ph_manager.get_medium_ph_range("soil")
    assert soil == [6.2, 7.0]
    assert ph_manager.recommend_medium_ph_adjustment(5.5, "soil") == "increase"
    assert ph_manager.recommend_medium_ph_adjustment(7.5, "soil") == "decrease"
    assert ph_manager.recommend_medium_ph_adjustment(6.5, "soil") is None
    assert ph_manager.recommended_ph_for_medium("coco") == 6.0
    assert ph_manager.get_medium_ph_range("unknown") == []


def test_soil_ph_functions():
    rng = ph_manager.get_soil_ph_range("citrus")
    assert rng == [6.0, 7.0]
    assert ph_manager.recommend_soil_ph_adjustment(5.5, "citrus") == "increase"
    assert ph_manager.recommend_soil_ph_adjustment(7.2, "citrus") == "decrease"
    assert ph_manager.recommend_soil_ph_adjustment(6.5, "citrus") is None
    assert ph_manager.get_soil_ph_range("unknown") == []


def test_classify_soil_ph():
    assert ph_manager.classify_soil_ph(5.5, "citrus") == "low"
    assert ph_manager.classify_soil_ph(7.2, "citrus") == "high"
    assert ph_manager.classify_soil_ph(6.5, "citrus") == "optimal"
    assert ph_manager.classify_soil_ph(6.5, "unknown") is None
