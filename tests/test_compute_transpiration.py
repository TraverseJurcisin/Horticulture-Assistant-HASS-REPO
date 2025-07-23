from plant_engine.compute_transpiration import (
    compute_transpiration,
    TranspirationMetrics,
    lookup_crop_coefficient,
    compute_transpiration_series,
)


def test_compute_transpiration_basic():
    profile = {"kc": 1.2, "canopy_m2": 0.25}
    env = {
        "temp_c": 25,
        "rh_pct": 50,
        "par_w_m2": 400,
        "wind_speed_m_s": 1.0,
        "elevation_m": 200,
    }
    result = compute_transpiration(profile, env)
    assert result["et0_mm_day"] == 8.54
    assert result["eta_mm_day"] == 10.25
    assert result["transpiration_ml_day"] == 2562.5


def test_transpiration_metrics_dataclass():
    metrics = TranspirationMetrics(8.0, 9.0, 1000.0)
    d = metrics.as_dict()
    assert d == {
        "et0_mm_day": 8.0,
        "eta_mm_day": 9.0,
        "transpiration_ml_day": 1000.0,
    }


def test_lookup_crop_coefficient():
    kc = lookup_crop_coefficient("lettuce", "vegetative")
    assert kc == 1.0


def test_lookup_crop_coefficient_case_insensitive():
    kc = lookup_crop_coefficient("LeTtuce", "VeGeTaTiVe")
    assert kc == 1.0


def test_compute_transpiration_series():
    profile = {"plant_type": "tomato", "stage": "vegetative", "canopy_m2": 0.5}
    envs = [
        {"temp_c": 24, "rh_pct": 65, "par_w_m2": 400},
        {"temp_c": 26, "rh_pct": 60, "par_w_m2": 420},
    ]
    series = compute_transpiration_series(profile, envs)
    assert len(series) == 2
    assert series[0]["et0_mm_day"] > 0
    assert series[1]["transpiration_ml_day"] > series[0]["transpiration_ml_day"]
