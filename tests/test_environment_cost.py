from plant_engine.environment_manager import estimate_environment_control_cost


def test_estimate_environment_control_cost():
    result = estimate_environment_control_cost(
        {"temp_c": 18, "co2_ppm": 350},
        "citrus",
        "seedling",
        hours=1.0,
        volume_m3=10.0,
    )
    assert set(result.keys()) == {"energy_kwh", "energy_cost", "co2_grams", "co2_cost"}
    assert result["energy_kwh"] >= 0
    assert result["co2_grams"] >= 0
