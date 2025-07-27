from custom_components.horticulture_assistant.utils.nutrient_use_efficiency import (
    get_efficiency_targets,
    score_efficiency,
)


def test_get_efficiency_targets():
    targets = get_efficiency_targets("tomato")
    assert targets["N"] == 5.0


def test_score_efficiency_perfect():
    eff = {"N": 5.0, "P": 8.0, "K": 6.5}
    score = score_efficiency(eff, "tomato")
    assert score == 100.0


def test_score_efficiency_partial():
    eff = {"N": 2.5}
    score = score_efficiency(eff, "tomato")
    assert 0 < score < 100
