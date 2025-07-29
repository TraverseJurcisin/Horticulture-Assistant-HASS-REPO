"""Utilities for pesticide withdrawal periods."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Mapping

from .utils import lazy_dataset, normalize_key

DATA_FILE = "pesticide_withdrawal_days.json"
REENTRY_FILE = "pesticide_reentry_intervals.json"
MOA_FILE = "pesticide_modes.json"
ROTATION_FILE = "pesticide_rotation_intervals.json"
PHYTO_FILE = "pesticide_phytotoxicity.json"
RATE_FILE = "pesticide_application_rates.json"
PRICE_FILE = "pesticide_prices.json"
ACTIVE_FILE = "pesticide_active_ingredients.json"
EFFICACY_FILE = "pesticide_efficacy.json"
PEST_ROTATION_FILE = "pest_rotation_moas.json"

# Cached withdrawal data mapping product names to waiting days
_DATA = lazy_dataset(DATA_FILE)
_REENTRY = lazy_dataset(REENTRY_FILE)
_MOA = lazy_dataset(MOA_FILE)
_ROTATION = lazy_dataset(ROTATION_FILE)
_PHYTO = lazy_dataset(PHYTO_FILE)
_RATES = lazy_dataset(RATE_FILE)
_PRICES = lazy_dataset(PRICE_FILE)
_ACTIVE = lazy_dataset(ACTIVE_FILE)
_EFFICACY = lazy_dataset(EFFICACY_FILE)
_PEST_ROTATION = lazy_dataset(PEST_ROTATION_FILE)

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
    "next_rotation_date",
    "suggest_rotation_plan",
    "get_phytotoxicity_risk",
    "is_safe_for_crop",
    "get_application_rate",
    "get_pesticide_price",
    "estimate_application_cost",
    "calculate_application_amount",
    "summarize_pesticide_restrictions",
    "get_active_ingredient_info",
    "list_active_ingredients",
    "get_pesticide_efficacy",
    "list_effective_pesticides",
    "recommend_rotation_products",
    "estimate_rotation_plan_cost",
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
    return _DATA().get(product.lower())


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
    return _REENTRY().get(product.lower())


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

    return _MOA().get(product.lower())


def list_known_pesticides() -> List[str]:
    """Return alphabetically sorted list of pesticides with MOA data."""

    return sorted(_MOA().keys())


def get_rotation_interval(product: str) -> int | None:
    """Return recommended rotation interval days for ``product``.

    The interval is looked up using the product's mode of action. ``None``
    is returned if either the MOA or rotation guideline is missing.
    """

    moa = get_mode_of_action(product)
    if moa is None:
        return None
    days = _ROTATION().get(moa.lower())
    return int(days) if isinstance(days, (int, float)) else None


def suggest_rotation_schedule(product: str, start_date: date, cycles: int) -> List[date]:
    """Return future application dates spaced by the rotation interval."""

    if cycles <= 0:
        raise ValueError("cycles must be positive")

    interval = get_rotation_interval(product)
    if interval is None:
        return []

    return [start_date + timedelta(days=interval * i) for i in range(cycles)]


def next_rotation_date(product: str, last_date: date) -> date | None:
    """Return the next application date after ``last_date``."""

    interval = get_rotation_interval(product)
    if interval is None:
        return None
    return last_date + timedelta(days=interval)


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

    crop = _PHYTO().get(normalize_key(plant_type))
    if not isinstance(crop, dict):
        return None
    return crop.get(product.lower())


def is_safe_for_crop(plant_type: str, product: str) -> bool:
    """Return ``False`` if ``product`` is marked high risk for ``plant_type``."""

    risk = get_phytotoxicity_risk(plant_type, product)
    return risk != "high"


def get_application_rate(product: str) -> float | None:
    """Return recommended grams or mL per liter for ``product``."""

    rate = _RATES().get(product.lower())
    try:
        return float(rate) if rate is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def get_pesticide_price(product: str) -> float | None:
    """Return price per unit for ``product`` if defined."""

    price = _PRICES().get(product.lower())
    try:
        return float(price) if price is not None else None
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def estimate_application_cost(product: str, volume_l: float) -> float:
    """Return cost of treating ``volume_l`` liters with ``product``."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    rate = get_application_rate(product)
    if rate is None:
        raise KeyError(f"Application rate for '{product}' is not defined")

    price = get_pesticide_price(product)
    if price is None:
        raise KeyError(f"Price for '{product}' is not defined")

    return round(price * rate * volume_l / 1000, 2)


def calculate_application_amount(product: str, volume_l: float) -> float:
    """Return grams or mL of ``product`` for ``volume_l`` solution."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")
    rate = get_application_rate(product)
    if rate is None:
        raise KeyError(f"Application rate for '{product}' is not defined")
    return round(rate * volume_l, 3)


def summarize_pesticide_restrictions(
    applications: Iterable[tuple[str, datetime]] | Iterable[tuple[str, date]]
) -> dict:
    """Return combined reentry and harvest restrictions.

    Parameters
    ----------
    applications:
        Sequence of ``(product, application_time)`` tuples. ``application_time``
        may be :class:`datetime.datetime` or :class:`datetime.date`. When a date
        is provided the time is assumed to be midnight for reentry calculations.

    Returns
    -------
    dict
        Mapping with optional ``"reentry_time"`` and ``"harvest_date"`` entries
        indicating the latest reentry datetime and earliest permissible harvest
        date after considering all applications.
    """

    dt_apps: list[tuple[str, datetime]] = []
    date_apps: list[tuple[str, date]] = []
    for product, applied in applications:
        if isinstance(applied, datetime):
            dt_apps.append((product, applied))
            date_apps.append((product, applied.date()))
        else:
            dt = datetime.combine(applied, datetime.min.time())
            dt_apps.append((product, dt))
            date_apps.append((product, applied))

    latest_reentry = calculate_reentry_window(dt_apps)
    earliest_harvest = calculate_harvest_window(date_apps)

    info: dict = {}
    if latest_reentry is not None:
        info["reentry_time"] = latest_reentry
    if earliest_harvest is not None:
        info["harvest_date"] = earliest_harvest
    return info


def get_active_ingredient_info(name: str) -> Dict[str, object] | None:
    """Return detailed info for a pesticide active ingredient."""

    return _ACTIVE().get(name.lower())


def list_active_ingredients() -> List[str]:
    """Return sorted list of known active ingredient names."""

    return sorted(_ACTIVE().keys())


def get_pesticide_efficacy(product: str, pest: str) -> float | None:
    """Return efficacy rating of ``product`` against ``pest`` if available."""

    data = _EFFICACY().get(product.lower())
    if not isinstance(data, Mapping):
        return None
    value = data.get(pest.lower())
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):  # pragma: no cover - invalid data
        return None


def list_effective_pesticides(pest: str) -> List[tuple[str, float]]:
    """Return products with efficacy ratings for ``pest`` sorted high to low."""

    results: list[tuple[str, float]] = []
    key = pest.lower()
    for product, ratings in _EFFICACY().items():
        if not isinstance(ratings, Mapping):
            continue
        rating = ratings.get(key)
        try:
            val = float(rating)
        except (TypeError, ValueError):
            continue
        results.append((product, val))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _products_for_moa(moa: str) -> list[str]:
    """Return products classified under the mode of action ``moa``."""

    key = normalize_key(moa)
    return [p for p, m in _MOA().items() if normalize_key(m) == key]


def recommend_rotation_products(pest: str, count: int = 3) -> list[str]:
    """Return up to ``count`` pesticide products rotated by MOA for ``pest``."""

    if count <= 0:
        raise ValueError("count must be positive")

    moas = _PEST_ROTATION().get(normalize_key(pest))
    if not isinstance(moas, Iterable):
        return []

    pest_key = normalize_key(pest)
    efficacies = _EFFICACY()
    chosen: list[str] = []
    for moa in moas:
        candidates = [
            p
            for p in _products_for_moa(moa)
            if isinstance(efficacies.get(p), Mapping)
            and pest_key in efficacies[p]
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda p: float(efficacies[p][pest_key]),
            reverse=True,
        )
        for prod in candidates:
            if prod not in chosen:
                chosen.append(prod)
                break
        if len(chosen) >= count:
            break

    return chosen


def estimate_rotation_plan_cost(
    plan: Iterable[tuple[str, date]], volume_l: float
) -> float:
    """Return total cost for executing a pesticide rotation plan."""

    if volume_l <= 0:
        raise ValueError("volume_l must be positive")

    total = 0.0
    for product, _ in plan:
        total += estimate_application_cost(product, volume_l)

    return round(total, 2)
