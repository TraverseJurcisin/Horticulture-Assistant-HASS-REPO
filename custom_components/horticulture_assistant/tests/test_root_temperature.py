from plant_engine.root_temperature import (
    get_uptake_factor,
    adjust_uptake,
    list_supported_plants,
    get_optimal_root_temperature,
    clear_cache,
)
from plant_engine.nutrient_manager import get_temperature_adjusted_levels


def test_get_uptake_factor_basic():
    assert get_uptake_factor(21) == 1.0
    assert get_uptake_factor(15) == 0.7
    assert 0.89 < get_uptake_factor(19) < 0.91


def test_adjust_uptake():
    uptake = {"N": 100, "P": 50}
    adjusted = adjust_uptake(uptake, 15)
    assert adjusted == {"N": 70.0, "P": 35.0}

    tomato_adjusted = adjust_uptake(uptake, 21, "tomato")
    assert tomato_adjusted == {"N": 85.0, "P": 42.5}


def test_plant_specific_optimum():
    tomato_factor = get_uptake_factor(21, "tomato")
    base_factor = get_uptake_factor(18)
    assert tomato_factor == base_factor


def test_temperature_adjusted_levels():
    levels = get_temperature_adjusted_levels("lettuce", "seedling", 15)
    assert levels["N"] == 68.0  # 80 * 0.85 (lettuce optimum 18C)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants and "lettuce" in plants


def test_get_optimal_root_temperature():
    assert get_optimal_root_temperature("tomato") == 24
    assert get_optimal_root_temperature("unknown") is None


def test_cache_clear():
    """get_uptake_factor results should update after clearing the cache."""
    first = get_uptake_factor(21)
    # change cached result by altering private data then clearing cache
    from plant_engine import root_temperature as rt

    rt._OPTIMA["test"] = 30
    clear_cache()
    second = get_uptake_factor(21, "test")
    assert first != second
