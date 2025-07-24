import pytest

from plant_engine.energy_manager import (
    get_energy_coefficient,
    estimate_hvac_energy,
    get_energy_price,
    estimate_hvac_cost,
)


def test_get_energy_coefficient():
    assert get_energy_coefficient("heating") == 0.5
    assert get_energy_coefficient("cooling") == 0.4
    assert get_energy_coefficient("unknown") == 0.0


def test_estimate_hvac_energy():
    # 2 degree difference for 12 hours with coefficient 0.5 kWh/degree-day
    kwh = estimate_hvac_energy(18, 20, 12, "heating")
    assert kwh == pytest.approx(0.5 * (2 * 12 / 24), 0.01)


def test_estimate_hvac_energy_invalid_hours():
    with pytest.raises(ValueError):
        estimate_hvac_energy(18, 20, 0, "heating")


def test_get_energy_price():
    assert get_energy_price("USD") == 0.12
    assert get_energy_price("eur") == 0.15
    assert get_energy_price("unknown") == 0.0


def test_estimate_hvac_cost():
    kwh = estimate_hvac_energy(18, 20, 12, "heating")
    cost = estimate_hvac_cost(18, 20, 12, "heating", "USD")
    assert cost == pytest.approx(kwh * 0.12, 0.01)
