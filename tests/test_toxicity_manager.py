from plant_engine.toxicity_manager import (
    list_supported_plants,
    get_toxicity_thresholds,
    check_toxicities,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "lettuce" in plants


def test_get_toxicity_thresholds():
    thresh = get_toxicity_thresholds("tomato")
    assert thresh["K"] == 350
    default = get_toxicity_thresholds("unknown")
    assert default["N"] == 200


def test_check_toxicities():
    current = {"N": 260, "K": 340, "Fe": 3}
    excess = check_toxicities(current, "tomato")
    assert excess["N"] == 10
    assert "K" not in excess
    assert "Fe" not in excess
