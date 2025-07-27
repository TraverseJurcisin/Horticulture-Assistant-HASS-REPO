from plant_engine.heat_memory import list_supported_plants, apply_heat_event


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "citrus" in plants
    assert "lettuce" in plants


def test_apply_heat_event():
    result = apply_heat_event("Citrus_001", "citrus", 3)
    assert result.lag_days == 3
    assert result.ec_reduction_pct == 15
    assert result.foliar_ca_days == 5


def test_apply_heat_event_default():
    result = apply_heat_event("Unknown_001", "unknown", 2)
    assert result.lag_days == 2
    assert result.ec_reduction_pct == 10
    assert result.foliar_ca_days == 3
