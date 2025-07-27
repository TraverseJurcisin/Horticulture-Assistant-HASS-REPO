from plant_engine import nutrient_losses


def test_estimate_total_loss_combines_sources():
    levels = {"N": 100, "P": 50}
    loss = nutrient_losses.estimate_total_loss(levels, plant_type="tomato")
    assert set(loss) == {"N", "P"}
    assert all(v >= 0 for v in loss.values())


def test_compensate_for_losses_adds_losses():
    levels = {"N": 100}
    result = nutrient_losses.compensate_for_losses(levels, plant_type="lettuce")
    assert result["N"] >= 100
