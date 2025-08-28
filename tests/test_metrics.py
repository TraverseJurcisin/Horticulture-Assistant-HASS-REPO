import importlib.util
from pathlib import Path

import pytest

# Import metrics module directly via file path to avoid importing the full
# Home Assistant integration package, which requires heavy dependencies.
_spec = importlib.util.spec_from_file_location(
    "metrics",
    Path(__file__).resolve().parent.parent
    / "custom_components/horticulture_assistant/engine/metrics.py",
)
metrics = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(metrics)


svp_kpa = metrics.svp_kpa
vpd_kpa = metrics.vpd_kpa
dew_point_c = metrics.dew_point_c
lux_to_ppfd = metrics.lux_to_ppfd
dli_from_ppfd = metrics.dli_from_ppfd


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


def test_saturation_vapor_pressure() -> None:
    """SVP baseline sanity check."""
    assert svp_kpa(25) == pytest.approx(3.1678, rel=1e-3)
