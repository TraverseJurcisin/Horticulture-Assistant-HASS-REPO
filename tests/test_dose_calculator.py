import importlib.util
import sys
from pathlib import Path
import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components/horticulture_assistant/utils/dose_calculator.py"
)
spec = importlib.util.spec_from_file_location("dose_calculator", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
DoseCalculator = mod.DoseCalculator


def test_calculate_mass_dose_ppm_alias():
    grams = DoseCalculator.calculate_mass_dose(150, 2, "ppm")
    assert grams == DoseCalculator.calculate_mass_dose(150, 2, "mg/L")


def test_calculate_mass_dose_units():
    assert DoseCalculator.calculate_mass_dose(1, 5, "g/L") == 5
    assert DoseCalculator.calculate_mass_dose(2, 1, "oz/gal") == pytest.approx(56.699, rel=1e-3)


def test_estimate_ppm_from_dose():
    ppm = DoseCalculator.estimate_ppm_from_dose(1, 1, "g/L")
    assert ppm == 1
    ppm = DoseCalculator.estimate_ppm_from_dose(0.5, 1, "ppm")
    assert ppm == 500


def test_convert_unit():
    assert DoseCalculator.convert_unit(1, "oz", "g") == 28.3495
    assert DoseCalculator.convert_unit(1000, "mL", "L") == 1
    with pytest.raises(ValueError):
        DoseCalculator.convert_unit(1, "foo", "bar")


def test_calculate_dilution_volume():
    vol = DoseCalculator.calculate_dilution_volume(1000, 100, 10, "ppm")
    assert vol == 1
    with pytest.raises(ValueError):
        DoseCalculator.calculate_dilution_volume(100, 100, 10)
    with pytest.raises(ValueError):
        DoseCalculator.calculate_dilution_volume(1000, 0, 10)
    with pytest.raises(ValueError):
        DoseCalculator.calculate_dilution_volume(1000, 100, -1)
    with pytest.raises(ValueError):
        DoseCalculator.calculate_dilution_volume(500, 600, 1)
