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

