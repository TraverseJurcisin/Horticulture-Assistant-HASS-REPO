from datetime import datetime
from typing import Dict, Optional


class ProductStorageMonitor:
    @staticmethod
    def is_expired(
        expiration_date: Optional[str],
        ignore_expiry: bool = False
    ) -> bool:
        """
        Checks if the product is expired.
        :param expiration_date: ISO format string (e.g., '2025-06-30')
        :param ignore_expiry: Whether to skip expiration check (for mineral products)
        """
        if ignore_expiry or not expiration_date:
            return False

        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()
            return datetime.today().date() > exp_date
        except ValueError:
            return False

    @staticmethod
    def flag_temperature_risk(
        temperature_c: float,
        ingredient_profile: Dict[str, Dict[str, float]]
    ) -> Optional[str]:
        """
        Checks if current temperature may compromise ingredients.
        Example ingredient_profile:
        {
            "Magnesium Sulfate": {"precip_temp": 10.0},
            "Urea": {"volatilize_temp": 30.0}
        }
        """
        for name, limits in ingredient_profile.items():
            if "precip_temp" in limits and temperature_c < limits["precip_temp"]:
                return f"{name} may precipitate at {temperature_c}°C"
            if "volatilize_temp" in limits and temperature_c > limits["volatilize_temp"]:
                return f"{name} may volatilize at {temperature_c}°C"
        return None

    @staticmethod
    def check_manufacturing_date(
        mfg_date: Optional[str],
        shelf_life_months: Optional[int] = None
    ) -> bool:
        """
        Checks if product is potentially outdated based on manufacturing date + shelf life.
        """
        if not mfg_date or not shelf_life_months:
            return False
        try:
            mfg_dt = datetime.strptime(mfg_date, "%Y-%m-%d")
            delta = datetime.today() - mfg_dt
            return delta.days > (shelf_life_months * 30)
        except ValueError:
            return False