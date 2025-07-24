"""Utilities for pesticide withdrawal periods."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

from .utils import load_dataset

DATA_FILE = "pesticide_withdrawal_days.json"
INFO_FILE = "pesticide_info.json"

# Cached withdrawal data mapping product names to waiting days
_DATA: Dict[str, int] = load_dataset(DATA_FILE)
# Extended info including toxicity class
_INFO: Dict[str, Dict[str, Any]] = load_dataset(INFO_FILE)

__all__ = [
    "get_pesticide_info",
    "get_withdrawal_days",
    "earliest_harvest_date",
    "adjust_harvest_date",
]


def get_pesticide_info(product: str) -> Dict[str, Any] | None:
    """Return pesticide information dictionary if available."""

    info = _INFO.get(product.lower())
    if info is not None:
        return dict(info)
    days = _DATA.get(product.lower())
    return {"withdrawal_days": days} if days is not None else None


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
    info = get_pesticide_info(product)
    if info is None:
        return None
    try:
        return int(info.get("withdrawal_days"))
    except (TypeError, ValueError):
        return None


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
