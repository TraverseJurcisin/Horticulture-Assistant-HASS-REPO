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
    calculate_vpd_series,
    photoperiod_for_target_dli,
    ppfd_for_target_dli,
    get_target_dli,
    get_target_vpd,
    get_target_photoperiod,
    humidity_for_target_vpd,
    recommend_photoperiod,
    recommend_light_intensity,
    evaluate_heat_stress,
    evaluate_cold_stress,
    evaluate_light_stress,
    evaluate_wind_stress,
    evaluate_humidity_stress,
    evaluate_stress_conditions,
    score_environment,
    score_environment_components,
    optimize_environment,
    calculate_environment_metrics,
    compare_environment,
    generate_environment_alerts,
    classify_environment_quality,
    normalize_environment_readings,
    summarize_environment,
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


def test_recommend_environment_adjustments_aliases():
    actions = recommend_environment_adjustments(
        {"temperature": 18, "humidity": 90, "light": 100, "co2": 700},
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
    assert round(result["absolute_humidity_g_m3"], 1) == round(
        calculate_absolute_humidity(18, 90), 1
    )
    assert result["target_vpd"] == (0.6, 0.8)
    assert result["ph_setpoint"] == 6.0
    assert result["ph_action"] is None
    assert result["target_dli"] is None
    assert result["photoperiod_hours"] is None
    assert result["target_photoperiod"] == (16, 18)

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
    assert result["target_photoperiod"] == (18, 20)


def test_optimize_environment_aliases():
    result = optimize_environment(
        {"temperature": 18, "humidity": 90},
        "citrus",
        "seedling",
    )
    assert result["setpoints"]["temp_c"] == 24
    assert result["adjustments"]["temperature"] == "increase"


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


def test_recommend_photoperiod():
    hours = recommend_photoperiod(500, "lettuce", "seedling")
    expected = photoperiod_for_target_dli(11, 500)
    assert hours == expected

    assert recommend_photoperiod(0, "lettuce") is None
    assert recommend_photoperiod(500, "unknown") is None


def test_ppfd_for_target_dli():
    ppfd = ppfd_for_target_dli(30, 15)
    assert round(ppfd, 2) == 555.56
    with pytest.raises(ValueError):
        ppfd_for_target_dli(-1, 15)
    with pytest.raises(ValueError):
        ppfd_for_target_dli(30, 0)


def test_recommend_light_intensity():
    ppfd = recommend_light_intensity(16, "lettuce", "seedling")
    expected = ppfd_for_target_dli(11, 16)
    assert round(ppfd, 2) == round(expected, 2)
    assert recommend_light_intensity(0, "lettuce") is None
    assert recommend_light_intensity(16, "unknown") is None


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


def test_get_environmental_targets_invalid_stage():
    default = get_environmental_targets("citrus")
    assert get_environmental_targets("citrus", "badstage") == default


def test_get_target_vpd():
    assert get_target_vpd("citrus", "seedling") == (0.6, 0.8)
    assert get_target_vpd("unknown") is None


def test_get_target_photoperiod():
    assert get_target_photoperiod("lettuce", "seedling") == (16, 18)
    assert get_target_photoperiod("unknown") is None


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


def test_evaluate_heat_stress():
    assert evaluate_heat_stress(32, 70, "citrus")
    assert not evaluate_heat_stress(26, 70, "citrus")


def test_evaluate_cold_stress():
    assert evaluate_cold_stress(2, "lettuce")
    assert not evaluate_cold_stress(10, "lettuce")


def test_optimize_environment_heat_stress():
    result = optimize_environment({"temp_c": 32, "humidity_pct": 70}, "citrus")
    assert result["heat_stress"] is True


def test_optimize_environment_cold_stress():
    result = optimize_environment({"temp_c": 2, "humidity_pct": 70}, "lettuce")
    assert result["cold_stress"] is True


def test_classify_environment_quality():
    good = {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450}
    poor = {"temp_c": 10, "humidity_pct": 30, "light_ppfd": 50, "co2_ppm": 1500}

    assert classify_environment_quality(good, "citrus", "seedling") == "good"
    assert classify_environment_quality(poor, "citrus", "seedling") == "poor"


def test_normalize_environment_readings_aliases():
    data = {"temperature": 25, "humidity": 70, "co2": "700", "ec": 1.2}
    result = normalize_environment_readings(data)
    assert result == {
        "temp_c": 25.0,
        "humidity_pct": 70.0,
        "co2_ppm": 700.0,
        "ec": 1.2,
    }

def test_normalize_environment_readings_temp_fahrenheit():
    data = {"temperature_f": 86}
    result = normalize_environment_readings(data)
    assert result == {"temp_c": 30.0}


def test_normalize_environment_readings_unknown_key():
    result = normalize_environment_readings({"foo": 1})
    assert result == {"foo": 1.0}


def test_summarize_environment():
    summary = summarize_environment({"temperature": 18, "humidity": 90}, "citrus", "seedling")
    assert summary["quality"] == "poor"
    assert summary["adjustments"]["temperature"] == "increase"
    assert summary["adjustments"]["humidity"] == "decrease"
    assert "vpd" in summary["metrics"]
    assert "score" in summary
    assert "stress" in summary


def test_summarize_environment_with_water_quality():
    summary = summarize_environment(
        {"temperature": 22, "humidity": 70},
        "citrus",
        "vegetative",
        water_test={"Na": 60, "Cl": 50},
    )
    assert summary["water_quality"]["rating"] == "fair"
    assert "score" in summary["water_quality"]


def test_evaluate_light_stress():
    assert evaluate_light_stress(8, "lettuce", "seedling") == "low"
    assert evaluate_light_stress(14, "lettuce", "seedling") == "high"
    assert evaluate_light_stress(11, "lettuce", "seedling") is None
    assert evaluate_light_stress(10, "unknown") is None


def test_optimize_environment_light_stress():
    result = optimize_environment({"dli": 8}, "lettuce", "seedling")
    assert result["light_stress"] == "low"


def test_evaluate_wind_stress():
    assert evaluate_wind_stress(16, "citrus") is True
    assert evaluate_wind_stress(5, "lettuce") is False
    assert evaluate_wind_stress(None, "citrus") is None


def test_evaluate_humidity_stress():
    assert evaluate_humidity_stress(30, "citrus") == "low"
    assert evaluate_humidity_stress(90, "citrus") == "high"
    assert evaluate_humidity_stress(60, "citrus") is None


def test_optimize_environment_wind_stress():
    result = optimize_environment({"wind": 16}, "citrus")
    assert result["wind_stress"] is True


def test_optimize_environment_humidity_stress():
    result = optimize_environment({"humidity_pct": 96}, "lettuce")
    assert result["humidity_stress"] == "high"


def test_evaluate_stress_conditions():
    stress = evaluate_stress_conditions(32, 70, 8, 16, "lettuce", "seedling")
    assert stress.heat is True
    assert stress.cold is False
    assert stress.light == "low"
    assert stress.wind is True
    assert stress.humidity is None

    stress_none = evaluate_stress_conditions(None, None, None, None, "citrus")
    assert stress_none.heat is None
    assert stress_none.humidity is None


def test_score_environment_components():
    scores = score_environment_components({"temp_c": 24, "humidity_pct": 70}, "citrus", "seedling")
    assert scores["temp_c"] == 100.0
    assert scores["humidity_pct"] == 100.0


def test_calculate_vpd_series():
    temps = [20, 22, 24]
    humidity = [70, 65, 60]
    expected = sum(calculate_vpd(t, h) for t, h in zip(temps, humidity)) / 3
    assert calculate_vpd_series(temps, humidity) == round(expected, 3)

    with pytest.raises(ValueError):
        calculate_vpd_series([20], [60, 70])

    with pytest.raises(ValueError):
        calculate_vpd_series([20], [-1])
