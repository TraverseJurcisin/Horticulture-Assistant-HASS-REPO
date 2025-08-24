from plant_engine.chill_risk import (
    forecast_chilling_risk,
    get_chill_buffer,
    list_supported_plants,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "monstera" in plants


def test_get_chill_buffer():
    assert get_chill_buffer("monstera") == 3
    assert get_chill_buffer("unknown") == 0


def test_forecast_chilling_risk():
    risk = forecast_chilling_risk("monstera", [6], [18], past_events=0)
    assert risk == "moderate"
    risk = forecast_chilling_risk("monstera", [4], [17], past_events=1)
    assert risk == "high"
