"""Helpers for calculating nutrient dosing volumes and concentrations."""

from typing import Dict, Literal, Tuple


class DoseCalculator:
    """Utility helpers for nutrient dosing calculations.

    All conversion factors are stored in :data:`CONVERSIONS` and the public
    methods simply apply these ratios. Values are rounded for user friendly
    output. The helpers are stateless and purely functional allowing easy use
    in automations and tests.
    """

    #: Conversion factors keyed by ``(from_unit, to_unit)`` tuples.
    CONVERSIONS: Dict[Tuple[str, str], float] = {
        ("oz", "g"): 28.3495,
        ("g", "oz"): 1 / 28.3495,
        ("mL", "L"): 0.001,
        ("L", "mL"): 1000,
        ("gal", "L"): 3.78541,
        ("L", "gal"): 1 / 3.78541,
    }

    @staticmethod
    def calculate_mass_dose(
        concentration: float,
        solution_volume: float,
        concentration_unit: Literal["mg/L", "g/L", "oz/gal", "ppm"]
    ) -> float:
        """Return grams of fertilizer for a target concentration.

        ``concentration`` is interpreted according to ``concentration_unit``.
        The alias ``"ppm"`` is accepted and treated as ``"mg/L"``.
        """

        unit = concentration_unit
        if unit == "ppm":
            unit = "mg/L"

        if unit == "mg/L":
            return round(concentration * solution_volume / 1000, 3)
        if unit == "g/L":
            return round(concentration * solution_volume, 3)
        if unit == "oz/gal":
            return round(concentration * solution_volume * 28.3495, 3)
        raise ValueError(f"Unsupported concentration unit: {concentration_unit}")

    @staticmethod
    def calculate_volume_dose(
        mass_dose: float,
        product_density: float
    ) -> float:
        """
        Converts a solid dose mass into volume dose for liquid fertilizer.
        :param mass_dose: dose in grams
        :param product_density: in g/mL
        :return: dose volume in mL
        """
        if product_density <= 0:
            raise ValueError("Product density must be greater than 0")
        return round(mass_dose / product_density, 3)

    @staticmethod
    def estimate_ppm_from_dose(
        mass_dose: float,
        solution_volume: float,
        concentration_unit: Literal["g/L", "mg/L", "ppm"]
    ) -> float:
        """Return the concentration derived from ``mass_dose``.

        The alias ``"ppm"`` may be provided and is treated as ``"mg/L"``.
        """

        unit = concentration_unit
        if unit == "ppm":
            unit = "mg/L"

        if unit == "mg/L":
            return round((mass_dose * 1000) / solution_volume, 2)
        if unit == "g/L":
            return round(mass_dose / solution_volume, 3)
        raise ValueError("Unsupported unit")

    @staticmethod
    def convert_unit(
        value: float,
        from_unit: str,
        to_unit: str
    ) -> float:
        """Return ``value`` converted from ``from_unit`` to ``to_unit``."""

        key = (from_unit, to_unit)
        if key in DoseCalculator.CONVERSIONS:
            return round(value * DoseCalculator.CONVERSIONS[key], 4)
        if from_unit == to_unit:
            return value
        raise ValueError(f"Unsupported conversion: {from_unit} -> {to_unit}")

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

        u = unit
        if u == "ppm":
            u = "mg/L"
        if u not in {"mg/L", "g/L"}:
            raise ValueError("Unsupported unit")

        if desired_concentration >= stock_concentration:
            raise ValueError("Stock concentration must exceed desired")

        v1 = (desired_concentration * final_volume_l) / stock_concentration
        return round(v1, 3)
