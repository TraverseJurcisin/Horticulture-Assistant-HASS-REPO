import plant_engine.environment_manager as em


def test_temperature_unit_sets():
    assert em.FAHRENHEIT_KEYS == {"temp_f", "soil_temp_f", "leaf_temp_f"}
    assert em.KELVIN_KEYS == {"temp_k", "soil_temp_k", "leaf_temp_k"}
