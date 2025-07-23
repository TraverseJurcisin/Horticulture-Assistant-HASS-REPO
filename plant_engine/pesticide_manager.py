"""Utilities for pesticide withdrawal periods."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict

from .utils import load_dataset

DATA_FILE = "pesticide_withdrawal_days.json"

# Cached withdrawal data mapping product names to waiting days
_DATA: Dict[str, int] = load_dataset(DATA_FILE)

__all__ = ["get_withdrawal_days", "earliest_harvest_date"]


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
