from plant_engine import ec_manager


def test_list_supported_plants():
    plants = ec_manager.list_supported_plants()
    assert "lettuce" in plants
    assert "tomato" in plants


def test_get_ec_range():
    rng = ec_manager.get_ec_range("lettuce", "seedling")
    assert rng == (0.8, 1.2)


def test_get_optimal_ec():
    assert ec_manager.get_optimal_ec("lettuce", "seedling") == 1.0
    assert ec_manager.get_optimal_ec("tomato", "fruiting") == 2.75


def test_get_stage_adjusted_ec_range():
    rng = ec_manager.get_stage_adjusted_ec_range("tomato", "fruiting")
    assert rng == (2.2, 3.85)


def test_classify_ec_level():
    assert ec_manager.classify_ec_level(0.7, "lettuce", "seedling") == "low"
    assert ec_manager.classify_ec_level(1.0, "lettuce", "seedling") == "optimal"
    assert ec_manager.classify_ec_level(1.3, "lettuce", "seedling") == "high"


def test_recommend_ec_adjustment():
    assert ec_manager.recommend_ec_adjustment(0.7, "lettuce", "seedling") == "increase"
    assert ec_manager.recommend_ec_adjustment(1.0, "lettuce", "seedling") == "none"
    assert ec_manager.recommend_ec_adjustment(1.3, "lettuce", "seedling") == "decrease"


def test_estimate_ec_adjustment_volume():
    ml = ec_manager.estimate_ec_adjustment_volume(0.6, 1.0, 1.0, "stock_a")
    assert ml == 4.0


def test_recommend_ec_correction_increase():
    result = ec_manager.recommend_ec_correction(0.6, "lettuce", "seedling", 1.0)
    assert result == {"stock_a": 2.67, "stock_b": 1.33}


def test_recommend_ec_correction_decrease():
    result = ec_manager.recommend_ec_correction(1.4, "lettuce", "seedling", 1.0)
    assert result == {"dilute_l": 0.4}
