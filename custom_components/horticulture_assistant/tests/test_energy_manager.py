import pytest

from plant_engine.energy_manager import (
    get_energy_coefficient,
    estimate_hvac_energy,
    estimate_hvac_cost,
    estimate_hvac_energy_series,
    estimate_hvac_cost_series,
    get_electricity_rate,
    estimate_lighting_energy,
    estimate_lighting_cost,
    get_emission_factor,
    estimate_lighting_emissions,
    estimate_hvac_emissions,
    estimate_hvac_emissions_series,
    get_light_efficiency,
    estimate_dli_from_power,
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


def test_estimate_hvac_energy_and_cost_series():
    temps = [20, 22, 18]
    energy = estimate_hvac_energy_series(18, temps, 4, "heating")
    cost = estimate_hvac_cost_series(18, temps, 4, "heating", region="california")
    assert len(energy) == len(temps)
    assert len(cost) == len(temps)
    assert cost[0] == pytest.approx(energy[0] * 0.18, abs=0.005)


def test_light_efficiency_and_dli():
    assert get_light_efficiency("led") == 2.5
    dli = estimate_dli_from_power(200, 5, "led")
    # 200W for 5h at 2.5 umol/J over 1 m^2 -> 9 mol
    assert dli == pytest.approx(9.0, 0.1)


def test_emission_factor_lookup():
    assert get_emission_factor("solar") == 0.05
    assert get_emission_factor("unknown") == 0.4


def test_lighting_emissions():
    kg = estimate_lighting_emissions(200, 5, "solar")
    assert kg == pytest.approx(0.05, 0.001)


def test_hvac_emissions_and_series():
    kg = estimate_hvac_emissions(18, 20, 12, "heating", source="coal")
    expected_energy = 0.5 * (2 * 12 / 24)
    assert kg == pytest.approx(expected_energy * 0.9, 0.001)

    temps = [20, 22]
    series = estimate_hvac_emissions_series(18, temps, 4, "heating", source="coal")
    expected_energy = round(0.5 * (2 * 4 / 24), 2)
    assert series[0] == pytest.approx(expected_energy * 0.9, 0.001)
