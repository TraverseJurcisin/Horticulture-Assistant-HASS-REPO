import math

from plant_engine.et_model import (
    adjust_et0_for_climate,
    calculate_et0,
    calculate_et0_series,
    calculate_eta,
    estimate_stage_et,
    get_et0_climate_adjustment,
)


def test_calculate_et0():
    et0 = calculate_et0(temperature_c=25, rh_percent=50, solar_rad_w_m2=400, wind_m_s=1.0, elevation_m=200)
    assert math.isclose(et0, 8.54, abs_tol=0.01)


def test_calculate_eta():
    assert calculate_eta(8.54, 1.2) == 10.25


def test_estimate_stage_et():
    et = estimate_stage_et("tomato", "vegetative", 7)
    assert math.isclose(et, 6.83, abs_tol=0.01)


def test_get_et0_climate_adjustment():
    assert math.isclose(get_et0_climate_adjustment("arid"), 1.2, abs_tol=0.01)
    assert get_et0_climate_adjustment("unknown") == 1.0


def test_adjust_et0_for_climate():
    assert adjust_et0_for_climate(5.0, "arid") == 6.0
    assert adjust_et0_for_climate(5.0, None) == 5.0


def test_calculate_et0_series():
    import pandas as pd

    temps = pd.Series([25, 26])
    rh = pd.Series([50, 55])
    solar = pd.Series([400, 420])
    series = calculate_et0_series(temps, rh, solar)
    # Compare to single value calculation
    assert series.iloc[0] == calculate_et0(25, 50, 400)
    assert series.iloc[1] == calculate_et0(26, 55, 420)
