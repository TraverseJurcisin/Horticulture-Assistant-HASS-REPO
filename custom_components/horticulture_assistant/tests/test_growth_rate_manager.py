from plant_engine.growth_rate_manager import estimate_growth, get_daily_growth_rate, list_supported_plants


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "citrus" in plants
    assert "lettuce" in plants


def test_get_daily_growth_rate():
    rate = get_daily_growth_rate("citrus", "vegetative")
    assert rate == 1.2
    assert get_daily_growth_rate("unknown", "stage") is None


def test_estimate_growth():
    grams = estimate_growth("lettuce", "vegetative", 3)
    assert grams == 4.5

    grams_zero = estimate_growth("unknown", "stage", 2)
    assert grams_zero == 0.0

    try:
        estimate_growth("lettuce", "vegetative", -1)
    except ValueError:
        pass
    else:
        raise AssertionError("negative days should raise")
