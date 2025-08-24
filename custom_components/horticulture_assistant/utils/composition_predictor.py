# Reference database of common fertilizer salts and their elemental contributions
# All values are percent by weight
KNOWN_COMPOUNDS = {
    "Ammonium Nitrate": {"N": 34.0},
    "Ammonium Phosphate": {"N": 11.0, "P": 8.8},
    "Potassium Nitrate": {"K": 38.0, "N": 13.0},
    "Monopotassium Phosphate": {"P": 22.7, "K": 28.7},
    "Magnesium Sulfate Heptahydrate": {"Mg": 9.8, "S": 12.9},
    "Calcium Nitrate": {"Ca": 19.0, "N": 15.5},
    "Sodium Molybdate": {"Mo": 39.6},
    "Zinc EDTA": {"Zn": 14.0},
    "Iron EDTA": {"Fe": 12.0},
    "Manganese EDTA": {"Mn": 13.0},
    "Copper EDTA": {"Cu": 15.0},
    "Boric Acid": {"B": 17.5},
    "Sodium Borate": {"B": 11.3},
    "Magnesium Nitrate": {"Mg": 9.5, "N": 10.9},
    "Potassium Sulfate": {"K": 44.9, "S": 18.4},
}


def predict_ingredient_ratios(
    derived_from_list: list[str],
    target_composition: dict[str, float],
    reference_table: dict[str, dict[str, float]] = KNOWN_COMPOUNDS,
) -> dict[str, float]:
    """
    Estimate relative contributions of fertilizer ingredients to match a guaranteed analysis.
    This uses a greedy approximation strategy (not a true optimization solver).

    Returns:
        Dict of {ingredient name: estimated % of formulation}
    """

    result = {ingredient: 0.0 for ingredient in derived_from_list}
    remaining = target_composition.copy()

    # Priority: fulfill most deficient elements first
    for element in sorted(remaining, key=remaining.get):
        # Find best-fit contributor for that element
        best_fit = None
        best_ratio = 0.0

        for ingredient in derived_from_list:
            if ingredient not in reference_table:
                continue

            contrib = reference_table[ingredient]
            if element in contrib:
                ratio = contrib[element] / sum(contrib.values())
                if ratio > best_ratio:
                    best_fit = ingredient
                    best_ratio = ratio

        # Apply contribution from best-fit
        if best_fit:
            ref_contrib = reference_table[best_fit]
            factor = remaining[element] / ref_contrib[element]
            result[best_fit] += round(factor * 100, 2)  # Express as % of product

            # Subtract element contributions
            for el in ref_contrib:
                if el in remaining:
                    remaining[el] -= ref_contrib[el] * factor
                    remaining[el] = max(remaining[el], 0.0)

    return result


def summarize_prediction(predict_result: dict[str, float]) -> str:
    return "\n".join(f"{k}: {v:.2f}%" for k, v in predict_result.items() if v > 0)
