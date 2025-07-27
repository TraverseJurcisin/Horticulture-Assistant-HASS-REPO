import math
from plant_engine.et_model import (
    calculate_et0,
    calculate_eta,
    estimate_stage_et,
)


def test_calculate_et0():
    et0 = calculate_et0(temperature_c=25, rh_percent=50, solar_rad_w_m2=400, wind_m_s=1.0, elevation_m=200)
    assert math.isclose(et0, 8.54, abs_tol=0.01)


def test_calculate_eta():
    assert calculate_eta(8.54, 1.2) == 10.25


def test_estimate_stage_et():
    et = estimate_stage_et("tomato", "vegetative", 7)
    assert math.isclose(et, 6.83, abs_tol=0.01)
