class TissueTestParser:
    def __init__(self):
        self.test_log: dict[str, dict] = {}
        self.thresholds: dict[
            str, dict[str, dict[str, float]]
        ] = {}  # plant_id → nutrient → range type

    def log_tissue_test(self, plant_id: str, raw_data: dict[str, str]):
        """
        Store raw test data (e.g., from user entry or file) and normalize to ppm.
        Example raw_data:
        {
            "N": "3.1%",
            "P": "0.4%",
            "Fe": "82 ppm",
            "Zn": "50 ppm",
            "Cd": "0.02 ppm"
        }
        """
        normalized = {}
        for nutrient, value in raw_data.items():
            ppm = self._normalize_to_ppm(value)
            if ppm is not None:
                normalized[nutrient] = ppm
        self.test_log[plant_id] = normalized

    def _normalize_to_ppm(self, value_str: str) -> float | None:
        """
        Convert input string to ppm. Supports % and ppm.
        """
        value_str = value_str.strip().lower()
        if "%" in value_str:
            try:
                value = float(value_str.replace("%", "").strip())
                return round(value * 10000, 2)  # 1% = 10,000 ppm
            except ValueError:
                return None
        elif "ppm" in value_str:
            try:
                return float(value_str.replace("ppm", "").strip())
            except ValueError:
                return None
        else:
            try:
                return float(value_str)
            except ValueError:
                return None

    def set_thresholds(self, plant_id: str, nutrient_thresholds: dict[str, dict[str, float]]):
        """
        Set deficiency/toxicity thresholds for a specific plant.
        Example:
        {
            "N": {"deficiency": 20000, "excess": 40000},
            "Fe": {"deficiency": 40, "excess": 300}
        }
        """
        self.thresholds[plant_id] = nutrient_thresholds

    def evaluate_test(self, plant_id: str) -> dict[str, str] | None:
        """
        Compare normalized test data against thresholds. Return flags.
        Output example:
        {"N": "Normal", "Fe": "Deficient", "Cd": "Toxic"}
        """
        if plant_id not in self.test_log or plant_id not in self.thresholds:
            return None

        evaluation = {}
        test_data = self.test_log[plant_id]
        thresholds = self.thresholds[plant_id]

        for nutrient, ppm in test_data.items():
            if nutrient not in thresholds:
                evaluation[nutrient] = "No Threshold"
                continue

            ranges = thresholds[nutrient]
            low = ranges.get("deficiency")
            high = ranges.get("excess")

            if low is not None and ppm < low:
                evaluation[nutrient] = "Deficient"
            elif high is not None and ppm > high:
                evaluation[nutrient] = "Toxic"
            else:
                evaluation[nutrient] = "Normal"

        return evaluation
