"""Helpers for calculating nutrient dosing volumes and concentrations."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Literal, Sequence, Tuple

try:
    from .unit_utils import convert
except ImportError:  # pragma: no cover - fallback for direct execution
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "unit_utils",
        Path(__file__).resolve().parent / "unit_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    convert = mod.convert  # type: ignore


class ConcentrationUnit(str, Enum):
    """Supported units for nutrient concentration."""

    MG_L = "mg/L"
    G_L = "g/L"
    OZ_GAL = "oz/gal"
    PPM = "ppm"

    @classmethod
    def normalize(cls, unit: str) -> "ConcentrationUnit":
        """Return enum member for ``unit`` allowing ``ppm`` as ``mg/L``."""
        if unit == cls.PPM.value:
            return cls.MG_L
        return cls(unit)


class DoseCalculator:
    """Utility helpers for nutrient dosing calculations.

    Unit conversions are handled by :mod:`unit_utils`. Values are rounded for
    user friendly
    output. The helpers are stateless and purely functional allowing easy use
    in automations and tests.
    """


    @staticmethod
    def calculate_mass_dose(
        concentration: float,
        solution_volume: float,
        concentration_unit: Literal["mg/L", "g/L", "oz/gal", "ppm"],
    ) -> float:
        """Return grams of fertilizer for a target concentration."""

        unit = ConcentrationUnit.normalize(concentration_unit)

        converters = {
            ConcentrationUnit.MG_L: lambda c, v: c * v / 1000,
            ConcentrationUnit.G_L: lambda c, v: c * v,
            ConcentrationUnit.OZ_GAL: lambda c, v: c * v * 28.3495,
        }

        if unit not in converters:
            raise ValueError(f"Unsupported concentration unit: {concentration_unit}")

        return round(converters[unit](concentration, solution_volume), 3)

    @staticmethod
    def calculate_volume_dose(
        mass_dose: float,
        product_density: float
    ) -> float:
        """Convert a solid dose mass into a liquid volume in milliliters."""
        if product_density <= 0:
            raise ValueError("Product density must be greater than 0")
        return round(mass_dose / product_density, 3)

    @staticmethod
    def estimate_ppm_from_dose(
        mass_dose: float,
        solution_volume: float,
        concentration_unit: Literal["g/L", "mg/L", "ppm"]
    ) -> float:
        """Return the concentration of ``mass_dose`` in the given units."""

        unit = ConcentrationUnit.normalize(concentration_unit)

        if unit == ConcentrationUnit.MG_L:
            return round((mass_dose * 1000) / solution_volume, 2)
        if unit == ConcentrationUnit.G_L:
            return round(mass_dose / solution_volume, 3)
        raise ValueError("Unsupported unit")

    @staticmethod
    def convert_unit(
        value: float,
        from_unit: str,
        to_unit: str
    ) -> float:
        """Return ``value`` converted from ``from_unit`` to ``to_unit``."""

        if from_unit == to_unit:
            return value

        return round(convert(value, from_unit, to_unit), 4)

    @staticmethod
    def calculate_dilution_volume(
        stock_concentration: float,
        desired_concentration: float,
        final_volume_l: float,
        unit: Literal["mg/L", "g/L", "ppm"] = "ppm",
    ) -> float:
        """Return stock solution volume (liters) required to dilute to target.

        The ``stock_concentration`` and ``desired_concentration`` are interpreted
        according to ``unit``. ``"ppm"`` is treated as ``"mg/L"``. The function
        implements the basic dilution equation ``C1 * V1 = C2 * V2`` where
        ``C1`` is the stock concentration, ``C2`` the desired concentration and
        ``V2`` the final solution volume. The returned value ``V1`` is rounded to
        three decimals.
        """

        if stock_concentration <= 0 or desired_concentration <= 0:
            raise ValueError("Concentrations must be positive")
        if final_volume_l <= 0:
            raise ValueError("final_volume_l must be positive")

        u = ConcentrationUnit.normalize(unit)
        if u not in {ConcentrationUnit.MG_L, ConcentrationUnit.G_L}:
            raise ValueError("Unsupported unit")

        if desired_concentration >= stock_concentration:
            raise ValueError("Stock concentration must exceed desired")

        v1 = (desired_concentration * final_volume_l) / stock_concentration
        return round(v1, 3)

    @staticmethod
    def blend_solutions(
        conc_a: float,
        vol_a: float,
        conc_b: float,
        vol_b: float,
        unit: Literal["mg/L", "g/L", "ppm"] = "ppm",
    ) -> float:
        """Return final concentration after mixing two solutions."""

        return DoseCalculator.blend_multiple_solutions(
            [(conc_a, vol_a), (conc_b, vol_b)], unit
        )

    @staticmethod
    def blend_multiple_solutions(
        solutions: Sequence[Tuple[float, float]],
        unit: Literal["mg/L", "g/L", "ppm"] = "ppm",
    ) -> float:
        """Return concentration after mixing many solutions.

        Each item in ``solutions`` is ``(concentration, volume)`` using ``unit``.
        ``ppm`` is treated as ``mg/L``. All volumes must be positive.
        """

        if not solutions:
            raise ValueError("No solutions provided")
        if any(v <= 0 for _, v in solutions):
            raise ValueError("Solution volumes must be positive")

        u = ConcentrationUnit.normalize(unit)
        if u not in {ConcentrationUnit.MG_L, ConcentrationUnit.G_L}:
            raise ValueError("Unsupported unit")

        # convert to mg/L for calculation
        def to_mg_l(c: float) -> float:
            return c * 1000 if u == ConcentrationUnit.G_L else c

        total_volume = sum(v for _, v in solutions)
        final_mg_l = sum(to_mg_l(c) * v for c, v in solutions) / total_volume

        return round(final_mg_l / 1000, 2) if unit == "g/L" else round(final_mg_l, 2)
