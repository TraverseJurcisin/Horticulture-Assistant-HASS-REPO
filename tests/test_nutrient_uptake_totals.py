from plant_engine.nutrient_uptake import estimate_stage_totals, estimate_total_uptake


def test_estimate_stage_totals():
    totals = estimate_stage_totals("lettuce", "vegetative")
    assert totals["N"] == 60 * 35
    assert totals["K"] == 80 * 35


def test_estimate_total_uptake():
    totals = estimate_total_uptake("lettuce")
    assert totals["N"] == 60 * 35 + 50 * 30
    assert totals["P"] == 20 * 35 + 15 * 30
    assert totals["K"] == 80 * 35 + 70 * 30
