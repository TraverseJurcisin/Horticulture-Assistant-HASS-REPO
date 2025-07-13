from typing import Dict, Tuple

TOXICITY_THRESHOLDS = {
    "Na": 50,  # ppm
    "Cl": 100,
    "B": 1.0,
    "EC": 1.0  # dS/m
}

def interpret_water_profile(water_test: Dict) -> Tuple[Dict, Dict]:
    """
    Given a water quality test result (in ppm), returns:
    - baseline nutrients
    - list of warnings if any values exceed limits
    """
    baseline = {}
    warnings = {}

    for ion, value in water_test.items():
        baseline[ion] = value

        if ion in TOXICITY_THRESHOLDS and value > TOXICITY_THRESHOLDS[ion]:
            warnings[ion] = {
                "value": value,
                "limit": TOXICITY_THRESHOLDS[ion],
                "issue": "Exceeds safe threshold"
            }

    return baseline, warnings
