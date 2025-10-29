import pandas as pd

from plant_engine.compute_transpiration import (
    TranspirationMetrics,
    compute_transpiration,
    compute_transpiration_dataframe,
    compute_transpiration_series,
    compute_weighted_transpiration_dataframe,
    lookup_crop_coefficient,
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
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    env1 = {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400}
    env2 = {"temp_c": 24, "rh_pct": 55, "par_w_m2": 420}
    series = [env1, env2]
    result = compute_transpiration_series(profile, series)
    assert result["et0_mm_day"] > 0
    assert result["eta_mm_day"] > 0
    assert result["transpiration_ml_day"] > 0


def test_compute_transpiration_series_weighted():
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    env1 = {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400}
    env2 = {"temp_c": 20, "rh_pct": 60, "par_w_m2": 350}
    series = [env1, env2]
    weighted = compute_transpiration_series(profile, series, weights=[2, 1])
    unweighted = compute_transpiration_series(profile, series)
    assert weighted["transpiration_ml_day"] != unweighted["transpiration_ml_day"]


def test_compute_transpiration_missing_env_defaults():
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    # Only provide temperature; other values should use DEFAULT_ENV
    result = compute_transpiration(profile, {"temp_c": 25})
    # Ensure calculation succeeded and returned positive transpiration
    assert result["transpiration_ml_day"] > 0


def test_compute_transpiration_auto_canopy():
    profile = {"plant_type": "strawberry", "stage": "flowering"}
    env = {"temp_c": 24, "rh_pct": 60, "par_w_m2": 420}
    result = compute_transpiration(profile, env)
    assert result["transpiration_ml_day"] > 0


def test_adjust_crop_coefficient():
    from plant_engine.compute_transpiration import adjust_crop_coefficient

    base_kc = 1.0
    # low humidity should increase kc
    adj = adjust_crop_coefficient(base_kc, 25.0, 30.0)
    assert adj > base_kc
    # high humidity should decrease kc
    adj2 = adjust_crop_coefficient(base_kc, 25.0, 90.0)
    assert adj2 < base_kc


def test_compute_transpiration_dataframe():
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    df = pd.DataFrame(
        [
            {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400},
            {"temp_c": 24, "rh_pct": 55, "par_w_m2": 420},
        ]
    )
    result = compute_transpiration_dataframe(profile, df)
    assert list(result.columns) == [
        "et0_mm_day",
        "eta_mm_day",
        "transpiration_ml_day",
    ]
    assert len(result) == 2
    assert result.iloc[0]["transpiration_ml_day"] > 0


def test_compute_transpiration_alias_support():
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    env = {"temperature": 25, "humidity": 50, "par": 400}
    result = compute_transpiration(profile, env)
    assert result["transpiration_ml_day"] > 0


def test_compute_weighted_transpiration_dataframe():
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    df = pd.DataFrame(
        [
            {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400},
            {"temp_c": 20, "rh_pct": 60, "par_w_m2": 350},
        ]
    )
    weights = [2, 1]
    result = compute_weighted_transpiration_dataframe(profile, df, weights)
    assert result["transpiration_ml_day"] > 0


def test_compute_transpiration_series_dataframe_input():
    profile = {"plant_type": "lettuce", "stage": "vegetative", "canopy_m2": 0.25}
    df = pd.DataFrame(
        [
            {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400},
            {"temp_c": 24, "rh_pct": 55, "par_w_m2": 420},
        ]
    )
    result = compute_transpiration_series(profile, df)
    assert result["transpiration_ml_day"] > 0
