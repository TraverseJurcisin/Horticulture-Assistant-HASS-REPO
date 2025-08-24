from plant_engine.heat_memory import (
    calculate_heat_memory_index,
    get_heat_memory_info,
    list_supported_plants,
    recommend_heat_recovery,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "citrus" in plants
    assert "lettuce" in plants


def test_get_heat_memory_info():
    info = get_heat_memory_info("citrus")
    assert info["lag_days"] == 3


def test_calculate_heat_memory_index():
    assert calculate_heat_memory_index("citrus", 3) == 2.0
    idx = calculate_heat_memory_index("lettuce", 3)
    assert round(idx, 2) == -1.2


def test_recommend_heat_recovery():
    rec = recommend_heat_recovery("citrus")
    assert rec["ec_adjustment_pct"] == -15
    assert rec["foliar_ca_days"] == 5
    assert recommend_heat_recovery("lettuce") == {}
