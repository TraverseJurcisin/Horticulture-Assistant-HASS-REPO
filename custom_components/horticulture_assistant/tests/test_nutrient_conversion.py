from ..engine.plant_engine.nutrient_conversion import get_conversion_factors, oxide_to_elemental


def test_conversion_factors_loaded():
    factors = get_conversion_factors()
    assert factors["P2O5"] == 0.44
    assert factors["K2O"] == 0.83


def test_oxide_to_elemental():
    assert oxide_to_elemental("P2O5", 10) == 4.4
    assert oxide_to_elemental("k2o", 5) == 4.15


def test_unknown_oxide():
    try:
        oxide_to_elemental("UNKNOWN", 1)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected KeyError")


def test_negative_amount():
    try:
        oxide_to_elemental("P2O5", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
