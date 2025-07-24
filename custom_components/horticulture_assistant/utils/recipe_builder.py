from typing import List, Dict
from custom_components.horticulture_assistant.utils.fertilizer_inventory import FertilizerProduct, FertilizerListing


class FertilizerDose:
    def __init__(self, listing: FertilizerListing, dose_amount: float, dose_unit: str):
        self.listing = listing
        self.dose_amount = dose_amount  # in g or mL
        self.dose_unit = dose_unit      # "g" or "mL"


class FertilizerRecipe:
    def __init__(self, recipe_id: str, target_volume_liters: float):
        self.recipe_id = recipe_id
        self.target_volume_liters = target_volume_liters
        self.doses: List[FertilizerDose] = []

    def add_dose(self, dose: FertilizerDose):
        self.doses.append(dose)

    def compute_total_cost(self) -> float:
        total = 0.0
        for dose in self.doses:
            cost_per_unit = dose.listing.cost_per_unit
            total += dose.dose_amount * cost_per_unit
        return round(total, 2)

    def compute_total_ppm(self, product_lookup: Dict[str, FertilizerProduct]) -> Dict[str, float]:
        ppm_totals = {}
        for dose in self.doses:
            product = product_lookup[dose.listing.product_id]
            # Convert dose to kg (solids) or L (liquids)
            if dose.dose_unit == "g":
                weight_kg = dose.dose_amount / 1000.0
            elif dose.dose_unit == "mL" and product.is_liquid:
                if product.density_kg_per_l:
                    weight_kg = (dose.dose_amount / 1000.0) * product.density_kg_per_l
                else:
                    continue  # skip if density missing
            else:
                continue

            solution_weight_kg = self.target_volume_liters  # assume water ~1 kg/L

            for element, pct in product.analysis.items():
                mg_of_element = pct * 0.01 * weight_kg * 1_000_000
                ppm = mg_of_element / solution_weight_kg
                ppm_totals[element] = ppm_totals.get(element, 0.0) + ppm

        return {k: round(v, 2) for k, v in ppm_totals.items()}

    def compute_ingredient_breakdown(self, product_lookup: Dict[str, FertilizerProduct]) -> Dict[str, Dict[str, float]]:
        result = {}
        for dose in self.doses:
            product = product_lookup[dose.listing.product_id]

            if dose.dose_unit == "g":
                dose_mass_kg = dose.dose_amount / 1000.0
            elif dose.dose_unit == "mL" and product.is_liquid:
                if not product.density_kg_per_l:
                    continue
                dose_mass_kg = (dose.dose_amount / 1000.0) * product.density_kg_per_l
            else:
                continue

            for ingredient, data in product.ingredients.items():
                try:
                    percent = float(data["amount"]) / 100 if data["unit"] == "percent_wt" else 0
                    mass_g = dose_mass_kg * percent * 1000
                    result[ingredient] = result.get(ingredient, {})
                    result[ingredient]["g"] = result[ingredient].get("g", 0.0) + round(mass_g, 2)
                except Exception:
                    continue

        return result
