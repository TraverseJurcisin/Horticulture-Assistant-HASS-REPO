"""Helpers for calculating nutrient dosing volumes and concentrations."""

from typing import Literal

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

        u = unit
        if u == "ppm":
            u = "mg/L"
        if u not in {"mg/L", "g/L"}:
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
        """Return final concentration after mixing two solutions.

        ``conc_a`` and ``conc_b`` are interpreted according to ``unit``.
        Both solutions must use the same units. ``"ppm"`` is treated as
        ``"mg/L"``. Volumes must be positive. The resulting concentration is
        returned in the same units, rounded to two decimals.
        """

        if vol_a <= 0 or vol_b <= 0:
            raise ValueError("Solution volumes must be positive")

        u = unit
        if u == "ppm":
            u = "mg/L"

        if u not in {"mg/L", "g/L"}:
            raise ValueError("Unsupported unit")

        # convert to mg/L for calculation
        if u == "g/L":
            conc_a *= 1000
            conc_b *= 1000

        total_volume = vol_a + vol_b
        final_mg_l = (conc_a * vol_a + conc_b * vol_b) / total_volume

        if unit == "g/L":
            return round(final_mg_l / 1000, 2)
        return round(final_mg_l, 2)

    # ------------------------------------------------------------------
    # Dataset assisted helpers
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_nutrient_dose(
        nutrient: str,
        ppm: float,
        volume_l: float,
        product: str,
    ) -> float:
        """Return grams of ``product`` required for a nutrient concentration.

        Purity factors are looked up in :data:`fertilizer_purity.json` via
        :func:`plant_engine.fertigation.get_fertilizer_purity`. ``ppm`` should
        be the desired nutrient concentration and ``volume_l`` the final
        solution volume. ``ValueError`` is raised if the product purity is
        unknown or if inputs are invalid.
        """

        if volume_l <= 0:
            raise ValueError("volume_l must be positive")

        # Import lazily so the calculator can be used without the full plant
        # engine installed.
        from plant_engine.fertigation import get_fertilizer_purity

        purity = get_fertilizer_purity(product).get(nutrient)
        if purity is None or purity <= 0:
            raise ValueError("Unknown product purity for nutrient")

        mg = ppm * volume_l
        return round(mg / 1000 / purity, 3)
