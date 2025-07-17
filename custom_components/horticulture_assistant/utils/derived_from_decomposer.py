from typing import Dict, List, Tuple


# Hypothetical molecular weights for common ingredients
MOLECULAR_WEIGHTS = {
    "Ammonium Nitrate": {"N": 0.33},
    "Potassium Sulfate": {"K": 0.45, "S": 0.18},
    "Magnesium Sulfate Heptahydrate": {"Mg": 0.098, "S": 0.13},
    "Calcium Nitrate": {"Ca": 0.19, "N": 0.15},
    "Monoammonium Phosphate": {"N": 0.11, "P": 0.26},
    "Monopotassium Phosphate": {"K": 0.28, "P": 0.22},
    "Magnesium Nitrate": {"Mg": 0.10, "N": 0.11},
    "Iron EDTA": {"Fe": 0.10},
    "Zinc EDTA": {"Zn": 0.10},
    "Copper EDTA": {"Cu": 0.10},
    "Manganese EDTA": {"Mn": 0.10},
    "Sodium Borate": {"B": 0.11},
    "Sodium Molybdate": {"Mo": 0.39},
    "EDTA": {"N": 0.00},  # Placeholder
    # Add more as needed
}


def decompose_derived_from(
    guaranteed_analysis: Dict[str, float],
    candidate_ingredients: List[str]
) -> List[Tuple[str, float]]:
    """
    Given a guaranteed analysis and a list of possible derived-from ingredients,
    attempt to infer the ingredient breakdown.

    Returns:
        List of tuples (ingredient, estimated inclusion rate as decimal fraction).
    """
    estimated_composition = []

    remaining_elements = guaranteed_analysis.copy()

    for ingredient in candidate_ingredients:
        if ingredient not in MOLECULAR_WEIGHTS:
            continue

        element_weights = MOLECULAR_WEIGHTS[ingredient]

        # Find the limiting element
        limiting_element = None
        limiting_ratio = float('inf')

        for element, ratio in element_weights.items():
            if element in remaining_elements and ratio > 0:
                possible_ratio = remaining_elements[element] / ratio
                if possible_ratio < limiting_ratio:
                    limiting_ratio = possible_ratio
                    limiting_element = element

        if limiting_element:
            estimated_composition.append((ingredient, round(limiting_ratio, 4)))
            # Subtract contribution
            for element, ratio in element_weights.items():
                if element in remaining_elements:
                    contribution = ratio * limiting_ratio
                    remaining_elements[element] = max(0, remaining_elements[element] - contribution)

    return estimated_composition