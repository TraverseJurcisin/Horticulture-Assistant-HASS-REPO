import pytest

from plant_engine.co2_manager import (
    list_sources,
    get_co2_price,
    estimate_injection_cost,
)


def test_list_sources_contains_compressed():
    assert "compressed" in list_sources()


def test_get_co2_price_positive():
    price = get_co2_price("compressed")
    assert price and price > 0


def test_estimate_injection_cost():
    cost = estimate_injection_cost(500, "compressed")
    assert cost > 0
    with pytest.raises(ValueError):
        estimate_injection_cost(-1)
    with pytest.raises(KeyError):
        estimate_injection_cost(100, "unknown")
