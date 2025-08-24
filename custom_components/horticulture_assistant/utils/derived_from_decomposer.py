"""Estimate fertilizer ingredients from a guaranteed analysis."""


# Simplified molecular weight fractions of common fertilizer ingredients.
MOLECULAR_WEIGHTS: dict[str, dict[str, float]] = {
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
    "EDTA": {"N": 0.00},
}


def decompose_derived_from(
    guaranteed_analysis: dict[str, float],
    candidate_ingredients: list[str],
) -> list[tuple[str, float]]:
    """Return estimated ingredient fractions for a fertilizer label.

    The ``candidate_ingredients`` list should contain possible "derived from"
    ingredients in the order they appear on the label. For each ingredient the
    function determines the limiting nutrient element and subtracts its
    contribution from the remaining nutrients. The result is a list of tuples
    ``(ingredient, fraction)`` where ``fraction`` represents the estimated
    inclusion rate as a decimal fraction.
    """

    estimated: list[tuple[str, float]] = []
    remaining = guaranteed_analysis.copy()

    for ingredient in candidate_ingredients:
        weights = MOLECULAR_WEIGHTS.get(ingredient)
        if not weights:
            continue

        limiting_ratio = float("inf")
        for element, ratio in weights.items():
            if element in remaining and ratio > 0:
                possible = remaining[element] / ratio
                if possible < limiting_ratio:
                    limiting_ratio = possible

        if limiting_ratio is float("inf"):
            continue

        estimated.append((ingredient, round(limiting_ratio, 4)))
        for element, ratio in weights.items():
            if element in remaining:
                remaining[element] = max(0.0, remaining[element] - ratio * limiting_ratio)

    return estimated
