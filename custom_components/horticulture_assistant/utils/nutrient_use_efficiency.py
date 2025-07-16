from typing import Dict, Optional


class NutrientUseEfficiency:
    def __init__(self):
        self.application_log: Dict[str, Dict] = {}
        self.tissue_log: Dict[str, Dict] = {}
        self.yield_log: Dict[str, float] = {}

    def log_fertilizer_application(self, plant_id: str, nutrient_mass: Dict[str, float]):
        """
        Record the total amount of nutrients applied to a plant.
        Example: {"N": 150, "P": 50, "K": 120}
        """
        if plant_id not in self.application_log:
            self.application_log[plant_id] = {}
        for nutrient, mass in nutrient_mass.items():
            self.application_log[plant_id][nutrient] = self.application_log[plant_id].get(nutrient, 0.0) + mass

    def log_tissue_test(self, plant_id: str, tissue_nutrient_mass: Dict[str, float]):
        """
        Record nutrient concentrations found in tissue for a given plant.
        Example: {"N": 9.2, "P": 2.3, "K": 7.4}
        """
        self.tissue_log[plant_id] = tissue_nutrient_mass

    def log_yield(self, plant_id: str, yield_mass: float):
        """
        Record the mass of yield produced for a given plant.
        """
        self.yield_log[plant_id] = yield_mass

    def compute_efficiency(self, plant_id: str) -> Optional[Dict[str, float]]:
        """
        Return nutrient use efficiency metrics, if all required data exists.
        - Apparent Recovery Efficiency (RE)
        - Physiological Efficiency (PE)
        - Internal Use Efficiency (IE)
        """
        if plant_id not in self.application_log or plant_id not in self.tissue_log or plant_id not in self.yield_log:
            return None

        applied = self.application_log[plant_id]
        tissue = self.tissue_log[plant_id]
        yield_mass = self.yield_log[plant_id]

        results = {}

        for nutrient in applied:
            applied_mass = applied.get(nutrient, 0.0)
            tissue_mass = tissue.get(nutrient, 0.0)

            if applied_mass == 0.0:
                continue

            recovery_efficiency = tissue_mass / applied_mass  # Fraction taken up
            physiological_efficiency = yield_mass / tissue_mass if tissue_mass else 0.0
            internal_efficiency = yield_mass / applied_mass

            results[nutrient] = round(internal_efficiency, 4)

        return results