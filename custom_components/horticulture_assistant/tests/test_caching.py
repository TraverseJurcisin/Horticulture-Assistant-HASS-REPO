from plant_engine.compute_transpiration import lookup_crop_coefficient
from plant_engine.environment_manager import (
    get_co2_price,
    EnvironmentGuidelines,
    EnvironmentMetrics,
    EnvironmentOptimization,
)
from plant_engine.irrigation_manager import (
    get_rain_capture_efficiency,
    get_irrigation_zone_modifier,
    get_crop_coefficient,
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


def test_get_rain_capture_efficiency_cache():
    get_rain_capture_efficiency.cache_clear()
    get_rain_capture_efficiency("mulch")
    hits = get_rain_capture_efficiency.cache_info().hits
    get_rain_capture_efficiency("mulch")
    assert get_rain_capture_efficiency.cache_info().hits == hits + 1


def test_get_irrigation_zone_modifier_cache():
    get_irrigation_zone_modifier.cache_clear()
    get_irrigation_zone_modifier("arid")
    hits = get_irrigation_zone_modifier.cache_info().hits
    get_irrigation_zone_modifier("arid")
    assert get_irrigation_zone_modifier.cache_info().hits == hits + 1


def test_get_crop_coefficient_cache():
    get_crop_coefficient.cache_clear()
    get_crop_coefficient("tomato", "vegetative")
    hits = get_crop_coefficient.cache_info().hits
    get_crop_coefficient("tomato", "vegetative")
    assert get_crop_coefficient.cache_info().hits == hits + 1
