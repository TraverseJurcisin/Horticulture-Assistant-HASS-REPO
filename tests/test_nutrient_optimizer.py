from plant_engine.nutrient_optimizer import optimize_targets, recommend_adjustments


def test_optimize_targets_ph_and_temp():
    targets = optimize_targets(
        "citrus",
        "fruiting",
        ph=5.5,
        root_temp_c=15,
        tags=["high-nitrogen"],
    )
    # Base fruiting N target is 120 ppm, high-nitrogen tag multiplies by 1.2 -> 144
    # pH 5.5 reduces availability of some nutrients; for N factor=1.0 (within range)
    # root temp 15C factor ~0.7 -> 144*0.7 = 100.8
    assert round(targets["N"], 1) == 100.8


def test_recommend_adjustments_basic():
    current = {"N": 70, "P": 20, "K": 50, "Ca": 10, "Mg": 5}
    adj = recommend_adjustments(current, "citrus", "fruiting")
    assert adj["N"] == 50
    assert adj["P"] == 20
    assert adj["K"] == 50
    assert adj["Ca"] == 30
    assert adj["Mg"] == 15
