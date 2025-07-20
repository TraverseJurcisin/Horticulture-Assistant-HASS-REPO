from plant_engine.compute_transpiration import compute_transpiration


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
