"""Helpers for validating fertilizer storage conditions."""

from datetime import datetime
from typing import Dict, Optional


class ProductStorageMonitor:
    """Utility class for common storage safety checks."""

    @staticmethod
    def is_expired(
        expiration_date: Optional[str],
        ignore_expiry: bool = False,
    ) -> bool:
        """Return ``True`` if ``expiration_date`` has passed."""

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
        ingredient_profile: Dict[str, Dict[str, float]],
    ) -> Optional[str]:
        """Return a warning string if ``temperature_c`` jeopardizes ingredients."""

        for name, limits in ingredient_profile.items():
            if "precip_temp" in limits and temperature_c < limits["precip_temp"]:
                return f"{name} may precipitate at {temperature_c}°C"
            if "volatilize_temp" in limits and temperature_c > limits["volatilize_temp"]:
                return f"{name} may volatilize at {temperature_c}°C"
        return None

    @staticmethod
    def check_manufacturing_date(
        mfg_date: Optional[str],
        shelf_life_months: Optional[int] = None,
    ) -> bool:
        """Return ``True`` if ``mfg_date`` is older than ``shelf_life_months``."""

        if not mfg_date or not shelf_life_months:
            return False
        try:
            mfg_dt = datetime.strptime(mfg_date, "%Y-%m-%d")
            delta = datetime.today() - mfg_dt
            return delta.days > (shelf_life_months * 30)
        except ValueError:
            return False


__all__ = [
    "ProductStorageMonitor",
]
