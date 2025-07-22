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
    calculate_absolute_humidity,
    calculate_dli,
    calculate_dli_series,
    photoperiod_for_target_dli,
    get_target_dli,
    get_target_vpd,
    humidity_for_target_vpd,
    score_environment,
    optimize_environment,
    calculate_environment_metrics,
    compare_environment,
    generate_environment_alerts,
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
        {"temp_c": 18, "humidity_pct": 90},
        "citrus",
        "seedling",
    )
    assert result["setpoints"]["temp_c"] == 24
    assert result["adjustments"]["temperature"] == "increase"
    assert round(result["vpd"], 3) == calculate_vpd(18, 90)
    assert round(result["dew_point_c"], 1) == round(calculate_dew_point(18, 90), 1)
    assert round(result["heat_index_c"], 1) == round(calculate_heat_index(18, 90), 1)
    assert round(result["absolute_humidity_g_m3"], 1) == round(calculate_absolute_humidity(18, 90), 1)
    assert result["target_vpd"] == (0.6, 0.8)
    assert result["ph_setpoint"] == 6.0
    assert result["ph_action"] is None
    assert result["target_dli"] is None
    assert result["photoperiod_hours"] is None

    result2 = optimize_environment(
        {"temp_c": 18, "humidity_pct": 90, "ph": 7.2},
        "citrus",
        "seedling",
    )
    assert result2["ph_setpoint"] == 6.0
    assert result2["ph_action"] == "decrease"
    assert result2["target_dli"] is None
    assert result2["photoperiod_hours"] is None
    assert result2["target_vpd"] == (0.6, 0.8)


def test_optimize_environment_with_dli():
    result = optimize_environment(
        {"temp_c": 20, "humidity_pct": 70, "light_ppfd": 500},
        "tomato",
        "seedling",
    )
    assert result["target_dli"] == (16, 20)
    mid = sum(result["target_dli"]) / 2
    expected_hours = photoperiod_for_target_dli(mid, 500)
    assert result["photoperiod_hours"] == expected_hours


def test_calculate_environment_metrics():
    metrics = calculate_environment_metrics(18, 90)
    assert metrics.vpd == calculate_vpd(18, 90)
    assert metrics.dew_point_c == calculate_dew_point(18, 90)
    assert metrics.heat_index_c == calculate_heat_index(18, 90)
    assert metrics.absolute_humidity_g_m3 == calculate_absolute_humidity(18, 90)
    empty = calculate_environment_metrics(None, None)
    assert all(
        getattr(empty, field) is None
        for field in ["vpd", "dew_point_c", "heat_index_c", "absolute_humidity_g_m3"]
    )


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


def test_get_target_vpd():
    assert get_target_vpd("citrus", "seedling") == (0.6, 0.8)
    assert get_target_vpd("unknown") is None


def test_calculate_absolute_humidity():
    ah = calculate_absolute_humidity(25, 50)
    assert round(ah, 1) == 11.5
    with pytest.raises(ValueError):
        calculate_absolute_humidity(25, -10)


def test_calculate_dli_series():
    series = [100] * 12 + [200] * 12
    dli = calculate_dli_series(series)
    expected = ((100 * 12) + (200 * 12)) * 3600 / 1_000_000
    assert round(dli, 2) == round(expected, 2)
    with pytest.raises(ValueError):
        calculate_dli_series([-1, 100])
    with pytest.raises(ValueError):
        calculate_dli_series([100], 0)


def test_compare_environment():
    targets = {"temp_c": [18, 22], "humidity_pct": [60, 80]}
    current = {"temperature": 20, "humidity": 70}
    result = compare_environment(current, targets)
    assert result["temp_c"] == "within range"
    assert result["humidity_pct"] == "within range"

    off = {"temp": 30, "rh": 40}
    result2 = compare_environment(off, targets)
    assert result2["temp_c"] == "above range"
    assert result2["humidity_pct"] == "below range"


def test_generate_environment_alerts():
    alerts = generate_environment_alerts(
        {"temp_c": 30, "humidity_pct": 40},
        "citrus",
        "seedling",
    )
    assert "temperature" in alerts
    assert alerts["temperature"].startswith("temperature above")
    assert "humidity" in alerts
    assert alerts["humidity"].startswith("humidity below")


def test_normalize_environment_readings():
    from plant_engine.environment_manager import normalize_environment_readings

    readings = normalize_environment_readings({"temperature": 21, "rh": 65})
    assert readings["temp_c"] == 21
    assert readings["humidity_pct"] == 65
