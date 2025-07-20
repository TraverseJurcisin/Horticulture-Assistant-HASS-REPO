from typing import Literal


class DoseCalculator:
    @staticmethod
    def calculate_mass_dose(
        concentration: float,
        solution_volume: float,
        concentration_unit: Literal["mg/L", "g/L", "oz/gal"]
    ) -> float:
        """
        Calculates mass of fertilizer product required for a given ppm target.
        Converts ppm units to grams based on the solution volume.

        :param concentration: target concentration (e.g., 150 ppm = 150 mg/L)
        :param solution_volume: total solution volume in liters or gallons
        :param concentration_unit: unit of input concentration
        :return: dose amount in grams
        """
        if concentration_unit == "mg/L":
            return round(concentration * solution_volume / 1000, 3)  # mg to grams
        elif concentration_unit == "g/L":
            return round(concentration * solution_volume, 3)
        elif concentration_unit == "oz/gal":
            return round(concentration * solution_volume * 28.3495, 3)  # oz to grams
        else:
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
        concentration_unit: Literal["g/L", "mg/L"]
    ) -> float:
        """
        Reverse of calculate_mass_dose: estimate the ppm from a known dose.
        :return: estimated ppm value
        """
        if concentration_unit == "mg/L":
            return round((mass_dose * 1000) / solution_volume, 2)
        elif concentration_unit == "g/L":
            return round(mass_dose / solution_volume, 3)
        else:
            raise ValueError("Unsupported unit")

    @staticmethod
    def convert_unit(
        value: float,
        from_unit: str,
        to_unit: str
    ) -> float:
        """
        Generic unit conversion (basic for now)
        """
        conversions = {
            ("oz", "g"): 28.3495,
            ("g", "oz"): 1 / 28.3495,
            ("mL", "L"): 0.001,
            ("L", "mL"): 1000,
            ("gal", "L"): 3.78541,
            ("L", "gal"): 1 / 3.78541,
        }
        key = (from_unit, to_unit)
        if key in conversions:
            return round(value * conversions[key], 4)
        elif from_unit == to_unit:
            return value
        else:
            raise ValueError(f"Unsupported conversion: {from_unit} -> {to_unit}")