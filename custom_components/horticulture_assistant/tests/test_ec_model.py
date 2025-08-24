from dafe.ec_model import calculate_ec_drift


def test_calculate_ec_drift():
    delta = calculate_ec_drift(
        ec_in=2.0, ec_out=1.5, volume_in=100, volume_out=20, volume_media=500
    )
    assert round(delta, 3) == round((2.0 * 100 - 1.5 * 20) / 500, 3)


def test_invalid_volumes():
    import pytest

    with pytest.raises(ValueError):
        calculate_ec_drift(2.0, 1.5, -1, 0, 500)
    with pytest.raises(ValueError):
        calculate_ec_drift(2.0, 1.5, 100, 0, 0)
