import importlib.util
from pathlib import Path

import pytest

# Import metrics module directly via file path to avoid importing the full
# Home Assistant integration package, which requires heavy dependencies.
_spec = importlib.util.spec_from_file_location(
    "metrics",
    Path(__file__).resolve().parent.parent / "custom_components/horticulture_assistant/engine/metrics.py",
)
metrics = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(metrics)


svp_kpa = metrics.svp_kpa
vpd_kpa = metrics.vpd_kpa
dew_point_c = metrics.dew_point_c
lux_to_ppfd = metrics.lux_to_ppfd
dli_from_ppfd = metrics.dli_from_ppfd
accumulate_dli = metrics.accumulate_dli
mold_risk = metrics.mold_risk
profile_status = metrics.profile_status
lux_model_ppfd = metrics.lux_model_ppfd


def test_vpd_and_dew_point() -> None:
    """VPD and dew point calculations should match known values."""
    assert vpd_kpa(25, 50) == pytest.approx(1.584, rel=1e-3)
    assert dew_point_c(25, 50) == pytest.approx(13.86, rel=1e-3)


def test_light_conversions() -> None:
    """Light conversion helpers should produce expected magnitudes."""
    ppfd = lux_to_ppfd(1000)
    assert ppfd == pytest.approx(18.5)
    dli = dli_from_ppfd(ppfd, 3600)
    assert dli == pytest.approx(0.0666, rel=1e-3)


def test_lux_model_ppfd_linear() -> None:
    """Calibrated lux model should evaluate using provided coefficients."""

    assert lux_model_ppfd("linear", [0.02, 1.0], 1000) == pytest.approx(21.0)


def test_saturation_vapor_pressure() -> None:
    """SVP baseline sanity check."""
    assert svp_kpa(25) == pytest.approx(3.1678, rel=1e-3)


def test_clamping_and_rounding() -> None:
    """Edge cases should be clamped and rounded appropriately."""
    assert lux_to_ppfd(-5) == 0.0
    assert vpd_kpa(25, -10) == vpd_kpa(25, 0)
    assert vpd_kpa(25, 150) == vpd_kpa(25, 100)
    assert dli_from_ppfd(500, 0) == 0.0


def test_mold_risk_index() -> None:
    """Mold risk should increase with humidity and clamp to range."""
    assert mold_risk(25, 60) == 0.0
    assert mold_risk(25, 95) == 6.0
    assert mold_risk(25, 75) == pytest.approx(1.1, rel=1e-2)


def test_accumulate_dli() -> None:
    """Accumulation helper should add new light to existing total."""
    assert accumulate_dli(1.0, 500, 3600) == pytest.approx(1.0 + dli_from_ppfd(500, 3600))


def test_profile_status() -> None:
    """Status classification should escalate with risk factors."""
    assert profile_status(0.0, 50.0) == "ok"
    assert profile_status(3.5, 50.0) == "warn"
    assert profile_status(5.0, 50.0) == "critical"
    assert profile_status(None, 5.0) == "critical"
