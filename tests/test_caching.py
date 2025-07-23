from plant_engine.compute_transpiration import lookup_crop_coefficient
from plant_engine.environment_manager import (
    get_co2_price,
    EnvironmentGuidelines,
    EnvironmentMetrics,
    EnvironmentOptimization,
)


def test_lookup_crop_coefficient_cache():
    lookup_crop_coefficient.cache_clear()
    lookup_crop_coefficient("lettuce", "vegetative")
    hits = lookup_crop_coefficient.cache_info().hits
    lookup_crop_coefficient("lettuce", "vegetative")
    assert lookup_crop_coefficient.cache_info().hits == hits + 1


def test_get_co2_price_cache():
    get_co2_price.cache_clear()
    get_co2_price("tank")
    hits = get_co2_price.cache_info().hits
    get_co2_price("tank")
    assert get_co2_price.cache_info().hits == hits + 1


def test_dataclass_slots():
    assert hasattr(EnvironmentGuidelines, "__slots__")
    assert hasattr(EnvironmentMetrics, "__slots__")
    assert hasattr(EnvironmentOptimization, "__slots__")
