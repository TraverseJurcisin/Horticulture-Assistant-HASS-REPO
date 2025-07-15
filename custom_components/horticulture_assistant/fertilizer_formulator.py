"""Fertilizer Formulator – Calculate elemental mass from fertilizer inputs."""

import json
import datetime

# Hardcoded fertilizer inventory — replace or load from YAML/HA in future
FERTILIZER_DB = {
    "foxfarm_grow_big": {
        "density_kg_per_l": 0.96,
        "guaranteed_analysis": {
            "N": 0.06,
            "P2O5": 0.04,
            "K2O": 0.04,
            "Mg": 0.006,
            "Fe": 0.001,
            "Mn": 0.0005,
            "Zn": 0.0005,
            "Cu": 0.0005,
            "B": 0.0002,
        },
    },
    "magriculture": {
        "density_kg_per_l": 1.0,
        "guaranteed_analysis": {
            "Mg": 0.098,
            "S": 0.129,
        },
    },
}


MOLAR_MASS_CONVERSIONS = {
    "P2O5": ("P", 0.436),
    "K2O": ("K", 0.830),
}


def convert_guaranteed_analysis(ga):
    """Convert P2O5 and K2O to elemental P and K."""
    result = {}
    for k, v in ga.items():
        if k in MOLAR_MASS_CONVERSIONS:
            element, factor = MOLAR_MASS_CONVERSIONS[k]
            result[element] = result.get(element, 0) + v * factor
        else:
            result[k] = result.get(k, 0) + v
    return result


def calculate_fertilizer_nutrients(plant_id, fertilizer_id, volume_ml):
    """Given fertilizer name and volume applied, return nutrient mass in mg."""
    if fertilizer_id not in FERTILIZER_DB:
        raise ValueError(f"Fertilizer '{fertilizer_id}' not found in inventory.")

    fert = FERTILIZER_DB[fertilizer_id]
    density = fert["density_kg_per_l"]
    ga = convert_guaranteed_analysis(fert["guaranteed_analysis"])

    volume_l = volume_ml / 1000
    weight_kg = volume_l * density
    weight_g = weight_kg * 1000

    output = {}
    for element, pct in ga.items():
        nutrient_mass_mg = weight_g * pct * 1000
        output[element] = round(nutrient_mass_mg, 2)

    return {
        "plant_id": plant_id,
        "fertilizer_id": fertilizer_id,
        "volume_ml": volume_ml,
        "datetime": datetime.datetime.now().isoformat(),
        "nutrients": output,
    }


def example_run():
    """Demonstration of the nutrient calculation pipeline."""
    payload = calculate_fertilizer_nutrients("citrus_001", "foxfarm_grow_big", 20)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    example_run()