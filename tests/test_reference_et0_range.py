from plant_engine.et_model import get_reference_et0_range


def test_get_reference_et0_range():
    assert get_reference_et0_range(1) == (1.5, 2.5)
    assert get_reference_et0_range(7) == (5.5, 7.5)


def test_get_reference_et0_range_invalid():
    import pytest
    with pytest.raises(ValueError):
        get_reference_et0_range(13)
