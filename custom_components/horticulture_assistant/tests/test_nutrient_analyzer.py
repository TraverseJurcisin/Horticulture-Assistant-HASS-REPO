import pytest

from custom_components.horticulture_assistant.utils.nutrient_analyzer import (
    ppm_to_mg,
    recommend_adjustments,
)


@pytest.mark.parametrize(
    "current,expected",
    [
        ({"N": 50, "P": 25, "K": 40}, {"N": 70, "P": 15, "K": 60}),
        ({"N": 120, "P": 40, "K": 110}, {"N": 0, "P": 0, "K": -10}),
    ],
)
def test_recommend_adjustments_basic(current, expected):
    result = recommend_adjustments(current, "citrus", "fruiting")
    for nutrient, value in expected.items():
        if value == 0:
            assert nutrient not in result
        else:
            assert pytest.approx(result[nutrient]) == value


def test_recommend_adjustments_with_volume():
    current = {"N": 50, "P": 25, "K": 40}
    result = recommend_adjustments(current, "citrus", "fruiting", volume_l=2)
    assert result["N"] == 70
    assert result["N_mg"] == 140
    assert result["K_mg"] == 120


def test_ppm_to_mg():
    assert ppm_to_mg(50, 1.5) == 75.0
