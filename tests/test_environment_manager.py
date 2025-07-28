import pytest
import math
import datetime

from plant_engine.environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    suggest_environment_setpoints,
    suggest_environment_setpoints_advanced,
    saturation_vapor_pressure,
    actual_vapor_pressure,
    calculate_vpd,
    calculate_dew_point,
    calculate_heat_index,
    calculate_heat_index_series,
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
    get_target_co2,
    get_target_light_intensity,
    get_target_light_ratio,
    calculate_co2_injection,
    recommend_co2_injection,
    get_co2_price,
    get_co2_efficiency,
    estimate_co2_cost,
    recommend_co2_injection_with_cost,
    calculate_co2_injection_series,
    calculate_co2_cost_series,
    humidity_for_target_vpd,
    recommend_photoperiod,
    recommend_light_intensity,
    evaluate_heat_stress,
    evaluate_cold_stress,
    evaluate_light_stress,
    evaluate_wind_stress,
    get_wind_action,
    recommend_wind_action,
    evaluate_humidity_stress,
    evaluate_vpd,
    recommend_vpd_action,
    evaluate_ph_stress,
    evaluate_stress_conditions,
    evaluate_soil_temperature_stress,
    evaluate_soil_ec_stress,
    evaluate_soil_ph_stress,
    evaluate_leaf_temperature_stress,
    score_environment,
    score_environment_series,
    score_environment_components,
    optimize_environment,
    calculate_environment_metrics,
    compare_environment,
    classify_value_range,
    _check_range,
    generate_environment_alerts,
    classify_environment_quality,
    classify_environment_quality_series,
    score_overall_environment,
    normalize_environment_readings,
    summarize_environment,
    summarize_environment_series,
    calculate_environment_metrics_series,
    average_environment_readings,
    calculate_environment_variance,
    calculate_environment_stddev,
    calculate_environment_deviation,
    calculate_environment_deviation_series,
    clear_environment_cache,
    get_target_soil_temperature,
    get_target_soil_ec,
    get_target_soil_ph,
    get_target_leaf_temperature,
    energy_optimized_setpoints,
    cost_optimized_setpoints,
    get_frost_dates,
    is_frost_free,
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
            "temp_c": 42,
            "humidity_pct": 90,
            "light_ppfd": 100,
            "co2_ppm": 700,
        },
        "citrus",
        "seedling",
    )
    assert actions["temperature"].startswith("Provide shade")
    assert actions["humidity"].startswith("Ventilate")
    assert actions["light"] == "increase"
    assert actions["co2"] == "decrease"


def test_recommend_environment_adjustments_aliases():
    actions = recommend_environment_adjustments(
        {"temperature": 42, "humidity": 90, "light": 100, "co2": 700},
        "citrus",
        "seedling",
    )
    assert actions["temperature"].startswith("Provide shade")
    assert actions["humidity"].startswith("Ventilate")
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
    assert setpoints["soil_moisture_pct"] == 40
    assert setpoints["soil_temp_c"] == 24
    assert setpoints["soil_ec"] == 1.15


def test_suggest_environment_setpoints_advanced_vpd_fallback(monkeypatch):
    import plant_engine.environment_manager as em

    monkeypatch.setattr(
        em,
        "get_environmental_targets",
        lambda *a, **k: {"temp_c": [20, 24]},
    )
    monkeypatch.setattr(em, "get_target_vpd", lambda *a, **k: (0.8, 1.2))

    result = suggest_environment_setpoints_advanced("foo", "bar")
    expected = em.humidity_for_target_vpd(22.0, 1.0)
    assert result["humidity_pct"] == expected


def test_energy_optimized_setpoints():
    normal = suggest_environment_setpoints("citrus", "seedling")
    result = energy_optimized_setpoints("citrus", "seedling", 20, 12)
    assert result["temp_c"] == 22
    for key, value in normal.items():
        if key != "temp_c":
            assert result[key] == value


def test_energy_optimized_setpoints_invalid():
    with pytest.raises(ValueError):
        energy_optimized_setpoints("citrus", "seedling", 20, 0)


def test_cost_optimized_setpoints():
    normal = suggest_environment_setpoints("citrus", "seedling")
    result = cost_optimized_setpoints("citrus", "seedling", 20, 12, region="default")
    assert result["temp_c"] == 22
    for key, value in normal.items():
        if key != "temp_c":
            assert result[key] == value


def test_cost_optimized_setpoints_invalid():
    with pytest.raises(ValueError):
        cost_optimized_setpoints("citrus", "seedling", 20, 0)


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


def test_calculate_heat_index_series():
    temps = [30, 32, 28]
    humidity = [70, 65, 80]
    expected = sum(
        calculate_heat_index(t, h) for t, h in zip(temps, humidity)
    ) / len(temps)
    assert calculate_heat_index_series(temps, humidity) == round(expected, 2)

    with pytest.raises(ValueError):
        calculate_heat_index_series([30], [50, 60])


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
    assert result["target_co2"] == (400, 600)
    assert result["target_light_ratio"] is None

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
    assert result2["target_co2"] == (400, 600)
    assert result2["target_light_ratio"] is None


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
    assert result["target_co2"] == (400, 600)
    assert result["target_light_ratio"] == 1.22


def test_optimize_environment_aliases():
    result = optimize_environment(
        {"temperature": 18, "humidity": 90},
        "citrus",
        "seedling",
    )
    assert result["setpoints"]["temp_c"] == 24
    assert result["adjustments"]["temperature"] == "increase"


def test_optimize_environment_zone():
    result = optimize_environment(
        {"temp_c": 20, "humidity_pct": 70},
        "lettuce",
        "seedling",
        zone="temperate",
    )
    assert result["setpoints"]["humidity_pct"] == 75
    assert result["setpoints"]["temp_c"] == 21


def test_calculate_environment_metrics():
    metrics = calculate_environment_metrics(18, 90)
    assert metrics.vpd == calculate_vpd(18, 90)
    assert metrics.dew_point_c == calculate_dew_point(18, 90)
    assert metrics.heat_index_c == calculate_heat_index(18, 90)
    assert metrics.absolute_humidity_g_m3 == calculate_absolute_humidity(18, 90)
    assert metrics.et0_mm_day is None
    assert metrics.eta_mm_day is None
    assert metrics.transpiration_ml_day is None
    empty = calculate_environment_metrics(None, None)
    assert all(
        getattr(empty, field) is None
        for field in ["vpd", "dew_point_c", "heat_index_c", "absolute_humidity_g_m3"]
    )


def test_environment_metrics_with_transpiration():
    env = {
        "temp_c": 25,
        "humidity_pct": 50,
        "par_w_m2": 400,
        "wind_speed_m_s": 1.0,
    }
    metrics = calculate_environment_metrics(
        25,
        50,
        env=env,
        plant_type="tomato",
        stage="vegetative",
    )
    assert metrics.et0_mm_day == 8.54
    assert metrics.eta_mm_day == 8.97
    assert metrics.transpiration_ml_day == 2242.5


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


def test_vpd_evaluation_and_action():
    low = evaluate_vpd(18, 90, "citrus", "seedling")
    assert low == "low"
    action_low = recommend_vpd_action(18, 90, "citrus", "seedling")
    assert "humidity" in action_low.lower() or "temperature" in action_low.lower()

    assert evaluate_vpd(22, 70, "citrus", "seedling") is None
    assert recommend_vpd_action(22, 70, "citrus", "seedling") is None

    high = evaluate_vpd(30, 30, "citrus", "seedling")
    assert high == "high"
    action_high = recommend_vpd_action(30, 30, "citrus", "seedling")
    assert "humidity" in action_high.lower() or "temperature" in action_high.lower()


def test_score_environment():
    current = {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450}
    score = score_environment(current, "citrus", "seedling")
    assert 90 <= score <= 100
    poor = {"temp_c": 10, "humidity_pct": 30, "light_ppfd": 50, "co2_ppm": 1500}
    low_score = score_environment(poor, "citrus", "seedling")
    assert low_score < score


def test_weighted_score_environment():
    base = {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450}
    bad_temp = {**base, "temp_c": 10}
    bad_hum = {**base, "humidity_pct": 40}
    score_temp = score_environment(bad_temp, "citrus", "seedling")
    score_hum = score_environment(bad_hum, "citrus", "seedling")
    assert score_temp < score_hum


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


def test_get_target_co2():
    assert get_target_co2("citrus", "seedling") == (400, 600)
    assert get_target_co2("unknown") is None


def test_get_target_light_ratio():
    assert get_target_light_ratio("lettuce", "seedling") == 0.67
    assert get_target_light_ratio("unknown", "seedling") is None


def test_get_target_light_intensity():
    assert get_target_light_intensity("citrus", "seedling") == (150, 300)
    assert get_target_light_intensity("unknown") is None


def test_calculate_co2_injection():
    target = get_target_co2("citrus", "seedling")
    grams = calculate_co2_injection(300, target, 100.0)
    assert grams > 0
    assert calculate_co2_injection(700, target, 100.0) == 0.0
    with pytest.raises(ValueError):
        calculate_co2_injection(300, target, -1)


def test_recommend_co2_injection():
    grams = recommend_co2_injection(300, "citrus", "seedling", 100.0)
    assert grams > 0
    assert recommend_co2_injection(700, "citrus", "seedling", 100.0) == 0.0
    assert recommend_co2_injection(300, "unknown", None, 100.0) == 0.0


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


def test_calculate_dli_series_generator():
    """Ensure generator inputs are supported."""

    def gen():
        for _ in range(24):
            yield 150

    expected = calculate_dli_series([150] * 24)
    assert calculate_dli_series(gen()) == expected


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


def test_classify_value_range_and_check_range():
    assert classify_value_range(10, (5, 15)) == "within range"
    assert classify_value_range(2, (5, 15)) == "below range"
    assert classify_value_range(20, (5, 15)) == "above range"

    assert _check_range(10, (5, 15)) is None
    assert _check_range(2, (5, 15)) == "increase"
    assert _check_range(20, (5, 15)) == "decrease"


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

    assert classify_environment_quality(good, "citrus", "seedling") == "excellent"
    assert classify_environment_quality(poor, "citrus", "seedling") == "poor"


def test_classify_environment_quality_custom():
    good = {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450}
    thresholds = {"good": 105, "fair": 80}
    assert (
        classify_environment_quality(good, "citrus", "seedling", thresholds) == "fair"
    )


def test_classify_environment_quality_series():
    series = [
        {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450},
        {"temp_c": 24, "humidity_pct": 72, "light_ppfd": 260, "co2_ppm": 460},
    ]
    result = classify_environment_quality_series(series, "citrus", "seedling")
    assert result == "excellent"


def test_classify_environment_quality_series_custom():
    series = [
        {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450},
        {"temp_c": 24, "humidity_pct": 72, "light_ppfd": 260, "co2_ppm": 460},
    ]
    thresholds = {"good": 105, "fair": 80}
    result = classify_environment_quality_series(
        series, "citrus", "seedling", thresholds
    )
    assert result == "fair"


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


def test_normalize_environment_readings_soil_temp_fahrenheit():
    data = {"soil_temp_f": 77}
    result = normalize_environment_readings(data)
    assert result == {"soil_temp_c": 25.0}


def test_normalize_environment_readings_temp_kelvin():
    data = {"temperature_k": 298.15}
    result = normalize_environment_readings(data)
    assert result == {"temp_c": 25.0}


def test_normalize_environment_readings_soil_temp_kelvin():
    data = {"soil_temp_k": 298.15}
    result = normalize_environment_readings(data)
    assert result == {"soil_temp_c": 25.0}


def test_normalize_environment_readings_leaf_temp_aliases():
    data = {"leaf_temp": 27, "leaf_temp_f": 86, "leaf_temp_k": 300}
    result = normalize_environment_readings(data)
    assert "leaf_temp_c" in result
    assert result["leaf_temp_c"] == pytest.approx(26.85, rel=1e-2)


def test_normalize_environment_readings_dataset_alias():
    data = {"temp_custom": 21}
    result = normalize_environment_readings(data)
    assert result == {"temp_c": 21.0}


def test_normalize_environment_readings_light_aliases():
    data = {"daily_light_integral": 18, "photoperiod": 14}
    result = normalize_environment_readings(data)
    assert result == {
        "dli": 18.0,
        "photoperiod_hours": 14.0,
    }


def test_normalize_environment_readings_unknown_key():
    result = normalize_environment_readings({"foo": 1})
    assert result == {"foo": 1.0}


def test_normalize_environment_readings_skip_invalid_values():
    data = {"temperature": float("nan"), "humidity": float("inf"), "co2": 700}
    result = normalize_environment_readings(data)
    assert result == {"co2_ppm": 700.0}


def test_normalize_environment_readings_exclude_unknown():
    data = {"foo": 1, "temperature": 25}
    result = normalize_environment_readings(data, include_unknown=False)
    assert result == {"temp_c": 25.0}


def test_average_environment_readings():
    series = [
        {"temp_c": 20, "humidity_pct": 60},
        {"temperature": 22, "humidity": 70},
    ]
    avg = average_environment_readings(series)
    assert avg["temp_c"] == pytest.approx(21)
    assert avg["humidity_pct"] == pytest.approx(65)


def test_calculate_environment_variance():
    series = [
        {"temp_c": 20, "humidity_pct": 70},
        {"temperature": 22, "humidity": 72},
        {"temp_c": 21, "humidity_pct": 74},
    ]
    var = calculate_environment_variance(series)
    assert var["temp_c"] == pytest.approx(0.667, rel=1e-3)
    assert var["humidity_pct"] == pytest.approx(2.667, rel=1e-3)


def test_calculate_environment_stddev():
    series = [
        {"temp_c": 20, "humidity_pct": 70},
        {"temperature": 22, "humidity": 72},
        {"temp_c": 21, "humidity_pct": 74},
    ]
    std = calculate_environment_stddev(series)
    assert std["temp_c"] == pytest.approx(math.sqrt(0.667), rel=1e-3)
    assert std["humidity_pct"] == pytest.approx(math.sqrt(2.667), rel=1e-3)


def test_calculate_environment_deviation():
    reading = {"temp_c": 22, "humidity_pct": 70}
    dev = calculate_environment_deviation(reading, "citrus", "seedling")
    assert dev["temp_c"] == pytest.approx(1.0)
    assert dev["humidity_pct"] == pytest.approx(0.0)


def test_calculate_environment_deviation_series():
    series = [
        {"temp_c": 22, "humidity_pct": 70},
        {"temp_c": 24, "humidity_pct": 70},
    ]
    dev = calculate_environment_deviation_series(series, "citrus", "seedling")
    assert dev["temp_c"] == pytest.approx(0.5)
    assert dev["humidity_pct"] == pytest.approx(0.0)


def test_calculate_environment_variance_empty():
    assert calculate_environment_variance([]) == {}


def test_summarize_environment():
    summary = summarize_environment(
        {"temperature": 18, "humidity": 90}, "citrus", "seedling", include_targets=True
    )
    assert summary["quality"] == "poor"
    assert summary["adjustments"]["temperature"] == "increase"
    assert summary["adjustments"]["humidity"].startswith("Ventilate")
    assert "vpd" in summary["metrics"]
    assert "score" in summary
    assert "stress" in summary
    assert "targets" in summary


def test_summarize_environment_with_water_quality():
    summary = summarize_environment(
        {"temperature": 22, "humidity": 70},
        "citrus",
        "vegetative",
        water_test={"Na": 60, "Cl": 50},
        include_targets=True,
    )
    assert summary["water_quality"]["rating"] == "fair"
    assert "score" in summary["water_quality"]


def test_optimize_environment_with_water_quality():
    result = optimize_environment(
        {"temperature": 22, "humidity": 70},
        "citrus",
        "vegetative",
        water_test={"Na": 60, "Cl": 50},
    )
    assert result["water_quality"]["rating"] == "fair"
    assert isinstance(result["score"], float)


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


def test_humidity_actions():
    from plant_engine import environment_manager as em

    assert em.get_humidity_action("low").startswith("Increase")
    assert em.get_humidity_action("HIGH").startswith("Ventilate")
    assert em.recommend_humidity_action(30, "citrus").startswith("Increase")
    assert em.recommend_humidity_action(60, "citrus") is None


def test_temperature_actions():
    from plant_engine import environment_manager as em

    assert em.get_temperature_action("cold").startswith("Increase")
    assert em.get_temperature_action("HOT").startswith("Provide")
    assert em.recommend_temperature_action(5, 70, "citrus").startswith("Increase")
    assert em.recommend_temperature_action(42, 70, "citrus").startswith("Provide")
    assert em.recommend_temperature_action(25, 50, "citrus") is None


def test_wind_actions():
    from plant_engine import environment_manager as em

    assert em.get_wind_action("HIGH").startswith("Install")
    assert em.recommend_wind_action(20, "citrus").startswith("Install")
    assert em.recommend_wind_action(5, "citrus") is None


def test_environment_strategies():
    from plant_engine import environment_manager as em

    assert "ventilation" in em.get_environment_strategy("temperature", "high")
    status = {"temperature": "high", "humidity": "low"}
    rec = em.recommend_environment_strategies(status)
    assert set(rec) == {"temperature", "humidity"}


def test_evaluate_ph_stress():
    assert evaluate_ph_stress(5.0, "citrus") == "low"
    assert evaluate_ph_stress(7.0, "citrus") == "high"
    assert evaluate_ph_stress(6.0, "citrus") is None


def test_optimize_environment_ph_stress():
    result = optimize_environment({"ph": 7.2}, "citrus")
    assert result["ph_stress"] == "high"


def test_optimize_environment_wind_stress():
    result = optimize_environment({"wind": 16}, "citrus")
    assert result["wind_stress"] is True


def test_optimize_environment_humidity_stress():
    result = optimize_environment({"humidity_pct": 96}, "lettuce")
    assert result["humidity_stress"] == "high"


def test_get_target_soil_temperature():
    assert get_target_soil_temperature("citrus", "germination") == (25, 32)


def test_get_target_leaf_temperature():
    assert get_target_leaf_temperature("citrus", "germination") == (26, 32)


def test_evaluate_soil_temperature_stress():
    assert evaluate_soil_temperature_stress(18, "citrus") == "cold"
    assert evaluate_soil_temperature_stress(30, "citrus") == "hot"
    assert evaluate_soil_temperature_stress(35, "citrus") == "hot"


def test_evaluate_leaf_temperature_stress():
    assert evaluate_leaf_temperature_stress(22, "citrus") == "cold"
    assert evaluate_leaf_temperature_stress(31, "citrus") == "hot"
    assert evaluate_leaf_temperature_stress(27, "citrus") is None


def test_get_target_soil_ec():
    assert get_target_soil_ec("lettuce", "seedling") == (0.6, 1.0)


def test_evaluate_soil_ec_stress():
    assert evaluate_soil_ec_stress(0.5, "lettuce", "seedling") == "low"
    assert evaluate_soil_ec_stress(1.1, "lettuce", "seedling") == "high"
    assert evaluate_soil_ec_stress(0.8, "lettuce", "seedling") is None


def test_get_target_soil_ph():
    assert get_target_soil_ph("citrus") == (6.0, 7.0)


def test_evaluate_soil_ph_stress():
    assert evaluate_soil_ph_stress(5.5, "citrus") == "low"
    assert evaluate_soil_ph_stress(7.2, "citrus") == "high"
    assert evaluate_soil_ph_stress(6.5, "citrus") is None


def test_evaluate_stress_conditions():
    stress = evaluate_stress_conditions(
        32, 70, 8, 7.5, 16, 45, 30, "lettuce", "seedling", 12, 6.5
    )
    assert stress.heat is True
    assert stress.cold is False
    assert stress.light == "low"
    assert stress.wind is True
    assert stress.humidity is None
    assert stress.soil_temp == "cold"
    assert stress.leaf_temp == "hot"

    stress_none = evaluate_stress_conditions(
        None, None, None, None, None, None, None, "citrus", soil_ph=None
    )
    assert stress_none.heat is None
    assert stress_none.humidity is None
    assert stress_none.soil_temp is None
    assert stress_none.leaf_temp is None


def test_score_environment_components():
    scores = score_environment_components(
        {"temp_c": 24, "humidity_pct": 70}, "citrus", "seedling"
    )
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


def test_calculate_vpd_series_generator():
    """Ensure VPD calculation works with generator inputs."""

    def temps():
        for t in [20, 22, 24]:
            yield t

    def hums():
        for h in [70, 65, 60]:
            yield h

    expected = sum(calculate_vpd(t, h) for t, h in zip([20, 22, 24], [70, 65, 60])) / 3
    assert calculate_vpd_series(temps(), hums()) == round(expected, 3)


def test_score_environment_series():
    series = [
        {"temp_c": 22, "humidity_pct": 70, "light_ppfd": 250, "co2_ppm": 450},
        {"temp_c": 24, "humidity_pct": 75, "light_ppfd": 260, "co2_ppm": 460},
    ]
    score = score_environment_series(series, "citrus", "seedling")
    assert 90 <= score <= 100


def test_score_environment_series_empty():
    assert score_environment_series([], "citrus") == 0.0


def test_score_environment_series_generator():
    records = [
        {"temp_c": 22, "humidity_pct": 70},
        {"temp_c": 24, "humidity_pct": 75},
    ]
    gen = (r for r in records)
    list_score = score_environment_series(records, "citrus")
    gen_score = score_environment_series(gen, "citrus")
    assert list_score == gen_score


def test_summarize_environment_series():
    series = [
        {"temp_c": 20, "humidity_pct": 70},
        {"temp_c": 22, "humidity_pct": 74},
    ]
    summary = summarize_environment_series(series, "citrus", "seedling")
    avg = summarize_environment(
        {"temp_c": 21, "humidity_pct": 72}, "citrus", "seedling"
    )
    assert summary["quality"] == avg["quality"]
    assert summary["metrics"]["vpd"] == avg["metrics"]["vpd"]


def test_calculate_environment_metrics_series():
    series = [
        {"temp_c": 20, "humidity_pct": 60},
        {"temp_c": 22, "humidity_pct": 65},
        {"temp_c": 21, "humidity_pct": 55},
    ]
    metrics = calculate_environment_metrics_series(series)
    avg_temp = (20 + 22 + 21) / 3
    avg_hum = (60 + 65 + 55) / 3
    assert metrics.vpd == calculate_vpd(avg_temp, avg_hum)


def test_summarize_environment_series_generator():
    records = [
        {"temp_c": 20, "humidity_pct": 70},
        {"temp_c": 22, "humidity_pct": 74},
    ]
    gen = (r for r in records)
    gen_summary = summarize_environment_series(gen, "citrus", "seedling")
    list_summary = summarize_environment_series(records, "citrus", "seedling")
    assert gen_summary == list_summary


def test_score_overall_environment():
    env = {
        "temp_c": 22,
        "humidity_pct": 70,
        "light_ppfd": 250,
        "co2_ppm": 450,
    }
    water = {"Na": 60}
    score = score_overall_environment(env, "citrus", "seedling", water)
    base = score_environment(env, "citrus", "seedling")
    assert score < base
    assert score > 90


def test_clear_environment_cache():
    data1 = get_environmental_targets("citrus", "seedling")
    price1 = get_co2_price("bulk_tank")
    clear_environment_cache()
    data2 = get_environmental_targets("citrus", "seedling")
    price2 = get_co2_price("bulk_tank")
    assert data1 == data2
    assert price1 == price2


def test_co2_price_and_cost():
    assert get_co2_price("bulk_tank") == 0.7
    assert estimate_co2_cost(1000, "bulk_tank") == 0.7
    assert get_co2_efficiency("cartridge") == 0.85
    grams, cost = recommend_co2_injection_with_cost(
        300, "citrus", "seedling", 100.0, "cartridge"
    )
    assert grams > 0
    assert cost == estimate_co2_cost(grams, "cartridge")


def test_estimate_co2_cost_negative():
    with pytest.raises(ValueError):
        estimate_co2_cost(-5, "bulk_tank")


def test_calculate_co2_injection_series():
    series = [300, 500, 700]
    grams = calculate_co2_injection_series(series, "citrus", "seedling", 50.0)
    assert len(grams) == 3
    assert grams[0] > grams[1] >= 0
    assert grams[2] == 0.0


def test_calculate_co2_cost_series():
    series = [300, 500, 700]
    costs = calculate_co2_cost_series(series, "citrus", "seedling", 50.0)
    assert len(costs) == 3
    assert costs[0] > costs[1] >= 0
    assert costs[2] == 0.0


def test_get_frost_dates_and_is_frost_free():
    dates = get_frost_dates("zone_6")
    assert dates == ("04-25", "10-15")

    assert is_frost_free(datetime.date(2024, 5, 1), "zone_6")
    assert not is_frost_free(datetime.date(2024, 3, 1), "zone_6")
