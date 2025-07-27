"""Utilities for pesticide withdrawal periods."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List

from .utils import load_dataset, normalize_key

DATA_FILE = "pesticide_withdrawal_days.json"
REENTRY_FILE = "pesticide_reentry_intervals.json"
MOA_FILE = "pesticide_modes.json"
ROTATION_FILE = "pesticide_rotation_intervals.json"
PHYTO_FILE = "pesticide_phytotoxicity.json"
RATE_FILE = "pesticide_application_rates.json"

# Cached withdrawal data mapping product names to waiting days
_DATA: Dict[str, int] = load_dataset(DATA_FILE)
_REENTRY: Dict[str, float] = load_dataset(REENTRY_FILE)
_MOA: Dict[str, str] = load_dataset(MOA_FILE)
_ROTATION: Dict[str, int] = load_dataset(ROTATION_FILE)
_PHYTO: Dict[str, Dict[str, str]] = load_dataset(PHYTO_FILE)
_RATES: Dict[str, float] = load_dataset(RATE_FILE)

__all__ = [
    "get_withdrawal_days",
    "earliest_harvest_date",
    "adjust_harvest_date",
    "calculate_harvest_window",
    "get_reentry_hours",
    "earliest_reentry_time",
    "calculate_reentry_window",
    "get_mode_of_action",
    "list_known_pesticides",
    "get_rotation_interval",
    "suggest_rotation_schedule",
    "suggest_rotation_plan",
    "get_phytotoxicity_risk",
    "is_safe_for_crop",
    "get_application_rate",
    "calculate_application_amount",
]


def get_withdrawal_days(product: str) -> int | None:
    """Return required waiting days after applying ``product``.

    Parameters
    ----------
    product: str
        Pesticide or treatment identifier.

    Returns
    -------
    int | None
        Days to wait before harvesting or ``None`` if unknown.
    """
    return _DATA.get(product.lower())


def earliest_harvest_date(product: str, application_date: date) -> date | None:
    """Return earliest harvest date after pesticide application."""
    days = get_withdrawal_days(product)
    if days is None:
        return None
    return application_date + timedelta(days=days)


def adjust_harvest_date(
    plant_type: str,
    start_date: date,
    product: str,
    application_date: date,
) -> date | None:
    """Return harvest date adjusted for pesticide withdrawal.

    The returned date is the later of :func:`growth_stage.predict_harvest_date`
    and :func:`earliest_harvest_date` for ``product``. ``None`` is returned if
    both dates are unknown.
    """

    from . import growth_stage

    predicted = growth_stage.predict_harvest_date(plant_type, start_date)
    wait_until = earliest_harvest_date(product, application_date)

    if predicted is None:
        return wait_until
    if wait_until is None:
        return predicted
    return max(predicted, wait_until)


def get_reentry_hours(product: str) -> float | None:
    """Return reentry interval in hours for ``product``."""
    return _REENTRY.get(product.lower())


def earliest_reentry_time(product: str, application_time: datetime) -> datetime | None:
    """Return earliest safe reentry ``datetime`` after pesticide application."""
    hours = get_reentry_hours(product)
    if hours is None:
        return None
    return application_time + timedelta(hours=float(hours))


def calculate_reentry_window(applications: Iterable[tuple[str, datetime]]) -> datetime | None:
    """Return latest reentry time from multiple pesticide applications."""
    latest: datetime | None = None
    for product, applied in applications:
        entry = earliest_reentry_time(product, applied)
        if entry is None:
            continue
        if latest is None or entry > latest:
            latest = entry
    return latest


def calculate_harvest_window(applications: Iterable[tuple[str, date]]) -> date | None:
    """Return earliest harvest date after multiple pesticide applications."""

    latest: date | None = None
    for product, applied in applications:
        harvest = earliest_harvest_date(product, applied)
        if harvest is None:
            continue
        if latest is None or harvest > latest:
            latest = harvest
    return latest


def get_mode_of_action(product: str) -> str | None:
    """Return the mode of action classification for ``product`` if known."""

    return _MOA.get(product.lower())


def list_known_pesticides() -> List[str]:
    """Return alphabetically sorted list of pesticides with MOA data."""

    return sorted(_MOA.keys())


def get_rotation_interval(product: str) -> int | None:
    """Return recommended rotation interval days for ``product``.

    The interval is looked up using the product's mode of action. ``None``
    is returned if either the MOA or rotation guideline is missing.
    """

    moa = get_mode_of_action(product)
    if moa is None:
        return None
    days = _ROTATION.get(moa.lower())
    return int(days) if isinstance(days, (int, float)) else None


def suggest_rotation_schedule(product: str, start_date: date, cycles: int) -> List[date]:
    """Return future application dates spaced by the rotation interval."""

    if cycles <= 0:
        raise ValueError("cycles must be positive")

    interval = get_rotation_interval(product)
    if interval is None:
        return []

    return [start_date + timedelta(days=interval * i) for i in range(cycles)]


def suggest_rotation_plan(
    products: Iterable[str], start_date: date
) -> List[tuple[str, date]]:
    """Return sequential application schedule for multiple products.

    Each product is scheduled after the rotation interval of the previous
    product. Unknown products are scheduled with no additional delay.

    Parameters
    ----------
    products:
        Iterable of pesticide product identifiers in the desired order of
        application.
    start_date:
        Date of the first application.
    """

    plan: List[tuple[str, date]] = []
    current_date = start_date
    for product in products:
        plan.append((product, current_date))
        interval = get_rotation_interval(product)
        if interval is None:
            interval = 0
        current_date += timedelta(days=interval)
    return plan


def get_phytotoxicity_risk(plant_type: str, product: str) -> str | None:
    """Return phytotoxicity risk level for ``product`` on ``plant_type``."""

    crop = _PHYTO.get(normalize_key(plant_type))
    if not isinstance(crop, dict):
        return None
    return crop.get(product.lower())


def is_safe_for_crop(plant_type: str, product: str) -> bool:
    """Return ``False`` if ``product`` is marked high risk for ``plant_type``."""

    risk = get_phytotoxicity_risk(plant_type, product)
    return risk != "high"


def get_application_rate(product: str) -> float | None:
    """Return recommended grams or mL per liter for ``product``."""

    rate = _RATES.get(product.lower())
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def calculate_application_amount(product: str, volume_l: float) -> float:
    """Return grams or mL of ``product`` for ``volume_l`` solution."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    rate = get_application_rate(product)
    if rate is None:
        raise KeyError(f"Application rate for '{product}' is not defined")
    return round(rate * volume_l, 3)
