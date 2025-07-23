from plant_engine.energy_manager import (
    get_energy_rate,
    estimate_lighting_energy,
    estimate_lighting_cost,
    estimate_heating_energy,
    estimate_heating_cost,
)


def test_estimate_lighting_energy_and_cost():
    energy = estimate_lighting_energy(12, 200)
    assert energy == 2.4
    cost = estimate_lighting_cost(12, 200, rate=0.1)
    assert cost == 0.24


def test_estimate_heating_energy_and_cost():
    energy = estimate_heating_energy(25, 15, 100, insulation_factor=2)
    assert energy == 25.0
    cost = estimate_heating_cost(25, 15, 100, insulation_factor=2, rate=0.2)
    assert cost == 5.0


def test_get_energy_rate_default():
    rate = get_energy_rate()
    assert isinstance(rate, float)
    assert rate > 0
