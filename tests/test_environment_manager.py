import pytest

from plant_engine.environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    suggest_environment_setpoints,
    saturation_vapor_pressure,
    actual_vapor_pressure,
    calculate_vpd,
    calculate_dew_point,
    calculate_heat_index,
    relative_humidity_from_dew_point,
    calculate_dli,
    calculate_dli_series,
    photoperiod_for_target_dli,
    get_target_dli,
    humidity_for_target_vpd,
    score_environment,
    optimize_environment,
    calculate_environment_metrics,
)


def test_get_environmental_targets_seedling():
    data = get_environmental_targets("citrus", "seedling")
    assert data["temp_c"] == [22, 26]
    assert data["humidity_pct"] == [60, 80]
    assert data["light_ppfd"] == [150, 300]
    assert data["co2_ppm"] == [400, 600]


def test_get_environmental_targets_case_insensitive():
    data = get_environmental_targets("CITRUS", "SeEdLiNg")
    assert data["temp_c"] == [22, 26]


def test_recommend_environment_adjustments():
    actions = recommend_environment_adjustments(
        {
            "temp_c": 18,
            "humidity_pct": 90,
            "light_ppfd": 100,
            "co2_ppm": 700,
        },
        "citrus",
        "seedling",
    )
    assert actions["temperature"] == "increase"
    assert actions["humidity"] == "decrease"
    assert actions["light"] == "increase"
    assert actions["co2"] == "decrease"


def test_recommend_environment_adjustments_no_data():
    actions = recommend_environment_adjustments({"temp_c": 20}, "unknown")
    assert actions == {}


def test_suggest_environment_setpoints():
    setpoints = suggest_environment_setpoints("citrus", "seedling")
    assert setpoints["temp_c"] == 24
    assert setpoints["humidity_pct"] == 70
    assert setpoints["light_ppfd"] == 225
    assert setpoints["co2_ppm"] == 500


def test_vapor_pressure_helpers():
    es = saturation_vapor_pressure(25)
    ea = actual_vapor_pressure(25, 50)
    assert round(es, 3) == 3.168
    assert round(ea, 3) == round(es * 0.5, 3)


def test_calculate_vpd():
    vpd = calculate_vpd(25, 50)
    # approx 1.584 kPa using standard formula
    assert round(vpd, 3) == 1.584


def test_calculate_vpd_invalid_humidity():
    with pytest.raises(ValueError):
        calculate_vpd(25, 120)


def test_calculate_dew_point():
    dp = calculate_dew_point(25, 50)
    # approx 13.8°C using Magnus formula
    assert round(dp, 1) == 13.8


def test_calculate_heat_index():
    hi = calculate_heat_index(32, 70)
    # approx 40.4°C for 32°C at 70% RH
    assert round(hi, 1) == 40.4


def test_calculate_heat_index_invalid():
    with pytest.raises(ValueError):
        calculate_heat_index(25, -10)


def test_relative_humidity_from_dew_point():
    rh = relative_humidity_from_dew_point(25, 13.8)
    assert round(rh) == 50
    with pytest.raises(ValueError):
        relative_humidity_from_dew_point(20, 30)


def test_optimize_environment():
    result = optimize_environment(
        {"temp_c": 18, "humidity_pct": 90, "ec": 2.5},
        "citrus",
        "seedling",
    )
    assert result["setpoints"]["temp_c"] == 24
    assert result["adjustments"]["temperature"] == "increase"
    assert round(result["vpd"], 3) == calculate_vpd(18, 90)
    assert round(result["dew_point_c"], 1) == round(calculate_dew_point(18, 90), 1)
    assert round(result["heat_index_c"], 1) == round(calculate_heat_index(18, 90), 1)
    assert result["ph_setpoint"] == 6.0
    assert result["ph_action"] is None
    assert result["ec_setpoint"] == 1.1
    assert result["ec_action"] == "decrease"

    result2 = optimize_environment(
        {"temp_c": 18, "humidity_pct": 90, "ph": 7.2, "ec": 1.1},
        "citrus",
        "seedling",
    )
    assert result2["ph_setpoint"] == 6.0
    assert result2["ph_action"] == "decrease"
    assert result2["ec_action"] is None


def test_calculate_environment_metrics():
    metrics = calculate_environment_metrics(18, 90)
    assert metrics.vpd == calculate_vpd(18, 90)
    assert metrics.dew_point_c == calculate_dew_point(18, 90)
    assert metrics.heat_index_c == calculate_heat_index(18, 90)
    empty = calculate_environment_metrics(None, None)
    assert empty.vpd is None and empty.dew_point_c is None and empty.heat_index_c is None


def test_calculate_dli():
    dli = calculate_dli(500, 16)
    assert round(dli, 1) == 28.8

    with pytest.raises(ValueError):
        calculate_dli(-1, 16)

    with pytest.raises(ValueError):
        calculate_dli(100, 0)


def test_photoperiod_for_target_dli():
    hours = photoperiod_for_target_dli(30, 500)
    assert round(hours, 2) == 16.67

    with pytest.raises(ValueError):
        photoperiod_for_target_dli(0, 500)
    with pytest.raises(ValueError):
        photoperiod_for_target_dli(30, -1)


def test_humidity_for_target_vpd():
    rh = humidity_for_target_vpd(25, 1.5)
    assert round(rh, 1) == 52.6

    with pytest.raises(ValueError):
        humidity_for_target_vpd(25, -0.1)
    with pytest.raises(ValueError):
        humidity_for_target_vpd(20, 3.0)


def test_score_environment():
    current = {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450}
    score = score_environment(current, "citrus", "seedling")
    assert 90 <= score <= 100
    poor = {"temp_c": 10, "humidity_pct": 30, "light_ppfd": 50, "co2_ppm": 1500}
    low_score = score_environment(poor, "citrus", "seedling")
    assert low_score < score


def test_get_target_dli():
    assert get_target_dli("lettuce", "seedling") == (10, 12)
    assert get_target_dli("unknown") is None


def test_get_target_dli_case_insensitive():
    assert get_target_dli("LeTtUcE", "SeEdLiNg") == (10, 12)


def test_calculate_dli_series():
    series = [100] * 12 + [200] * 12
    dli = calculate_dli_series(series)
    expected = ((100 * 12) + (200 * 12)) * 3600 / 1_000_000
    assert round(dli, 2) == round(expected, 2)
    with pytest.raises(ValueError):
        calculate_dli_series([-1, 100])
    with pytest.raises(ValueError):
        calculate_dli_series([100], 0)
