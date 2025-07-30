import pytest

from custom_components.horticulture_assistant.utils.nutrient_mix_optimizer import optimize_mix


def test_optimize_mix_basic():
    result = optimize_mix("tomato", "vegetative", 10.0)
    assert isinstance(result.schedule, dict)
    assert result.cost >= 0
    assert result.diagnostics["volume_l"] == 10.0


def test_optimize_mix_num_plants():
    result = optimize_mix("tomato", "vegetative", 5.0, num_plants=2)
    assert result.diagnostics["num_plants"] == 2


def test_optimize_mix_invalid_volume():
    with pytest.raises(ValueError):
        optimize_mix("tomato", "vegetative", 0)
