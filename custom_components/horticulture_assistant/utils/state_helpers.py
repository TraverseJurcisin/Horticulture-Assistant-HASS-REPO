"""Utility helpers for working with Home Assistant state values."""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Iterable
from statistics import mean, median

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "coerce_numeric_value",
    "get_numeric_state",
    "normalize_entities",
    "aggregate_sensor_values",
    "parse_entities",
]

# Pre-compiled pattern used to extract a numeric portion from a string. This
# avoids recompiling the regex for every state lookup and handles optional
# sign and decimal point.
_NUM_RE = re.compile(r"[-+]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:[eE][-+]?\d+)?")
# Treat commas, semicolons and any whitespace (including newlines) as
# delimiters so multiline strings from UI forms are handled gracefully.
_SEP_RE = re.compile(r"[;,\s]+")
# Collapse all whitespace characters (including non-breaking spaces) when
# normalising numeric strings.
_WHITESPACE_RE = re.compile(r"\s+")
# Normalise common Unicode sign variants (e.g. MINUS SIGN, EN DASH) so numeric
# parsing treats them identically to the ASCII ``-``/``+`` characters.
_SIGN_TRANSLATION = str.maketrans(
    {
        "−": "-",  # U+2212 MINUS SIGN
        "﹣": "-",  # U+FE63 SMALL HYPHEN-MINUS
        "－": "-",  # U+FF0D FULLWIDTH HYPHEN-MINUS
        "–": "-",  # U+2013 EN DASH (sometimes used for negatives)
        "—": "-",  # U+2014 EM DASH (defensive)
        "＋": "+",  # U+FF0B FULLWIDTH PLUS SIGN
        "﹢": "+",  # U+FE62 SMALL PLUS SIGN
    }
)


def _normalise_numeric_string(value: str) -> str:
    """Normalise ``value`` into a float-compatible numeric string."""

    trimmed = value.strip()
    if not trimmed:
        return trimmed

    collapsed = _WHITESPACE_RE.sub("", trimmed).translate(_SIGN_TRANSLATION)
    sign = ""
    if collapsed and collapsed[0] in "+-":
        sign, collapsed = collapsed[0], collapsed[1:]

    if not collapsed:
        return sign

    if "," not in collapsed:
        if collapsed.count(".") > 1:
            segments = collapsed.split(".")
            head, *tail = segments
            if head and all(segment.isdigit() for segment in segments):
                if tail and all(len(segment) == 3 for segment in tail):
                    return f"{sign}{head}{''.join(tail)}"
        return f"{sign}{collapsed}"

    if "." in collapsed:
        last_dot = collapsed.rfind(".")
        last_comma = collapsed.rfind(",")
        if last_dot > last_comma:
            return f"{sign}{collapsed.replace(',', '')}"
        collapsed = collapsed.replace(".", "")

    if collapsed.count(",") > 1:
        return f"{sign}{collapsed.replace(',', '')}"

    whole, frac = collapsed.split(",", 1)
    digits_whole = whole.isdigit()
    digits_frac = frac.isdigit()

    if digits_frac:
        if digits_whole and len(frac) == 3 and whole:
            return f"{sign}{whole}{frac}"
        if not whole:
            return f"{sign}0.{frac}"
        if digits_whole:
            return f"{sign}{whole}.{frac}"

    if digits_whole and not frac:
        return f"{sign}{whole}"

    return f"{sign}{collapsed.replace(',', '')}"


def coerce_numeric_value(value: object) -> float | None:
    """Return ``value`` as a ``float`` when it represents a numeric reading."""

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None

    text = str(value).strip()
    if not text:
        return None

    try:
        normalised = _normalise_numeric_string(text)
        number = float(normalised)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        match = _NUM_RE.search(text)
        if not match:
            return None
        fragment = match.group(0)
        try:
            normalised = _normalise_numeric_string(fragment)
            number = float(normalised)
            return number if math.isfinite(number) else None
        except (ValueError, TypeError):
            return None


def get_numeric_state(hass: HomeAssistant, entity_id: str) -> float | None:
    """Return the numeric state of ``entity_id`` or ``None`` if unavailable.

    The helper accepts values with optional units appended, such as
    ``"25 °C"`` or ``"5.5pH"``. Non-numeric states return ``None`` and a
    debug message is logged. Values like ``"unknown"`` or ``"unavailable````
    are also treated as missing.
    """

    state = hass.states.get(entity_id)
    if not state:
        _LOGGER.debug("State unavailable: %s", entity_id)
        return None

    raw_state = state.state
    if isinstance(raw_state, str) and raw_state.lower() in {"unknown", "unavailable"}:
        _LOGGER.debug("State unavailable: %s", entity_id)
        return None

    coerced = coerce_numeric_value(raw_state)
    if coerced is not None:
        return coerced

    value = str(raw_state).strip()
    _LOGGER.warning("State of %s is not numeric: %s", entity_id, value)
    return None


def parse_entities(val: str | Iterable[str] | None) -> list[str]:
    """Return a list of unique, stripped entity IDs from ``val``.

    ``val`` may be a string containing comma/semicolon-delimited IDs or any
    iterable. Whitespace-only and duplicate entries are removed while
    preserving the original order. An empty or ``None`` input yields an empty
    list.
    """

    if not val:
        return []

    if isinstance(val, str):
        parts = (p.strip() for p in _SEP_RE.split(val))
    else:
        parts = ("" if v is None else (v.strip() if isinstance(v, str) else str(v).strip()) for v in val)

    return list(dict.fromkeys(filter(None, parts)))


def normalize_entities(val: str | Iterable[str] | None, default: str) -> list[str]:
    """Return a list of entity IDs from ``val`` or ``default``.

    String inputs may be comma or semicolon separated. Whitespace is stripped
    and duplicate entries removed while preserving order. Passing ``None`` or
    an empty value results in ``[default]``.
    """

    entities = parse_entities(val)
    return entities or [default]


def aggregate_sensor_values(hass: HomeAssistant, entity_ids: str | Iterable[str] | None) -> float | None:
    """Return the average or median of numeric sensor values.

    String inputs may contain multiple IDs separated by commas or semicolons.
    Up to two sensors are averaged while three or more use the median.
    Duplicate IDs are ignored, and non-numeric or unavailable sensors are
    skipped. ``None`` is returned if no valid states are found or ``entity_ids``
    is empty.
    """

    ids = parse_entities(entity_ids)
    if not ids:
        return None

    values = [v for eid in ids if (v := get_numeric_state(hass, eid)) is not None]
    if not values:
        return None
    return median(values) if len(values) > 2 else mean(values)
