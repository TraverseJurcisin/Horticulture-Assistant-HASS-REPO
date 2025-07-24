"""Utilities for pesticide withdrawal periods."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List

from .utils import load_dataset

DATA_FILE = "pesticide_withdrawal_days.json"
REENTRY_FILE = "pesticide_reentry_intervals.json"
MOA_FILE = "pesticide_modes.json"

# Cached withdrawal data mapping product names to waiting days
_DATA: Dict[str, int] = load_dataset(DATA_FILE)
_REENTRY: Dict[str, float] = load_dataset(REENTRY_FILE)
_MOA: Dict[str, str] = load_dataset(MOA_FILE)

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
