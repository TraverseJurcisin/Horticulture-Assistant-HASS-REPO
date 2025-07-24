import pytest

from plant_engine.energy_manager import (
    get_energy_coefficient,
    estimate_hvac_energy,
    get_electricity_rate,
    estimate_lighting_energy,
    estimate_lighting_cost,
    get_monthly_electricity_rate,
    estimate_lighting_cost_monthly,
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


def test_monthly_electricity_rate_lookup():
    assert get_monthly_electricity_rate("california", 1) == 0.20
    assert get_monthly_electricity_rate("california", 5) == 0.19
    # falls back to average when month missing
    assert get_monthly_electricity_rate("unknown", 3) == 0.12


def test_estimate_lighting_cost_monthly():
    cost = estimate_lighting_cost_monthly(100, 10, 1, "california")
    energy = estimate_lighting_energy(100, 10)
    assert cost == pytest.approx(energy * 0.20, 0.01)
