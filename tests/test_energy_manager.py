import pytest

from plant_engine.energy_manager import (
    get_energy_coefficient,
    estimate_hvac_energy,
    estimate_hvac_cost,
    get_electricity_rate,
    estimate_lighting_energy,
    estimate_lighting_cost,
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


def test_electricity_rate_lookup():
    assert get_electricity_rate("california") == 0.18
    assert get_electricity_rate("unknown") == 0.12


def test_estimate_lighting_energy_and_cost():
    energy = estimate_lighting_energy(200, 5)
    assert energy == 1.0
    cost = estimate_lighting_cost(200, 5, "california")
    assert cost == pytest.approx(1.0 * 0.18, 0.01)


def test_estimate_lighting_energy_invalid():
    with pytest.raises(ValueError):
        estimate_lighting_energy(0, 5)


def test_estimate_hvac_cost():
    # 2 degree difference for 12 hours using heating system with rate 0.18
    cost = estimate_hvac_cost(18, 20, 12, "heating", region="california")
    expected_kwh = 0.5 * (2 * 12 / 24)
    assert cost == pytest.approx(expected_kwh * 0.18, 0.01)
