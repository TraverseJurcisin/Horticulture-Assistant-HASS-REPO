import logging
from datetime import datetime, timedelta
from pathlib import Path

from plant_engine.utils import load_json, save_json

from custom_components.horticulture_assistant.utils.path_utils import data_path

_LOGGER = logging.getLogger(__name__)


def export_growth_yield(
    plant_id: str,
    base_path: str = "plants",
    output_path: str = "analytics",
    force: bool = False,
) -> list[dict]:
    """
    Export daily growth and yield time series for a given plant.

    Reads the plant's profile data and logs to compile a daily timeline of
    growth metrics (e.g., vegetative index or canopy size) and yield history.
    Each daily entry includes:
      - date (YYYY-MM-DD)
      - growth_metric (if available for that day)
      - yield_quantity (if a yield event occurred on that day)
      - cumulative_yield (total yield up to and including that day)

    Only one entry per day is produced (multiple yield events on the same day
    are aggregated). By default days without recorded growth or yield changes
    are omitted for brevity. Set ``force=True`` to include every day in the
    range, inserting empty entries when needed.

    The resulting time series is written to
    ``output_path/{plant_id}_growth_yield.json``. The list of daily entries is
    returned for further use.
    """
    # Determine plant directory and data files
    base_dir = Path(base_path)
    plant_dir = base_dir / str(plant_id)
    yield_log_file = plant_dir / "yield_tracking_log.json"

    # Load yield tracking log
    yield_entries = []
    if yield_log_file.is_file():
        data = load_json(yield_log_file)
        if isinstance(data, list):
            yield_entries = data
        elif data is not None:
            _LOGGER.warning(
                "Yield log for plant %s is not a list; ignoring content.", plant_id
            )
    else:
        _LOGGER.warning(
            "Yield tracking log not found for plant %s at %s", plant_id, yield_log_file
        )

    # Aggregate yield quantities by date
    yield_by_date = {}
    for entry in yield_entries:
        if not isinstance(entry, dict):
            continue
        ts = entry.get("timestamp") or entry.get(
            "date"
        )  # allow "date" key fallback if used
        if not ts:
            continue
        try:
            # Parse date (ignore time)
            ts_str = str(ts)
            if ts_str.endswith("Z"):
                # Remove trailing Z (UTC designator) if present for compatibility
                ts_str = ts_str[:-1]
            date_obj = datetime.fromisoformat(ts_str)
        except Exception as err:
            _LOGGER.warning(
                "Unrecognized timestamp format in yield log (%s): %s", ts, err
            )
            continue
        date_str = date_obj.date().isoformat()
        try:
            qty = float(entry.get("yield_quantity", 0))
        except (ValueError, TypeError):
            qty = 0
        # Sum multiple yields on the same date
        yield_by_date[date_str] = yield_by_date.get(date_str, 0) + qty

    # Load growth trend data (if available)
    growth_by_date = {}
    growth_trends_file = Path(data_path(None, "growth_trends.json"))
    if growth_trends_file.is_file():
        try:
            growth_trends = load_json(growth_trends_file)
        except Exception as exc:
            _LOGGER.warning("Failed to load growth trends: %s", exc)
            growth_trends = {}
        if isinstance(growth_trends, dict) and plant_id in growth_trends:
            plant_growth = growth_trends.get(plant_id)
            if isinstance(plant_growth, dict):
                for d, metrics in plant_growth.items():
                    # Use date string as key
                    date_key = str(d)
                    if isinstance(metrics, dict):
                        # Prefer 'vgi' (vegetative growth index) if present
                        if "vgi" in metrics:
                            gm_value = metrics["vgi"]
                        else:
                            # Fallbacks: 'growth_index' or canopy size if present
                            gm_value = (
                                metrics.get("growth_index")
                                or metrics.get("canopy")
                                or metrics.get("canopy_size")
                            )
                        # Convert to float if possible
                        try:
                            if gm_value is not None:
                                gm_value = float(gm_value)
                        except Exception:
                            pass
                        growth_by_date[date_key] = gm_value
                    elif metrics is not None:
                        # If metrics is a direct numeric value
                        try:
                            gm_val = float(metrics)
                        except Exception:
                            gm_val = None
                        growth_by_date[date_key] = gm_val
    else:
        _LOGGER.info(
            "Growth trends file not found at %s; proceeding without growth metrics.",
            growth_trends_file,
        )

    # Determine the set of dates to include
    dates_with_data = set(yield_by_date.keys()) | set(growth_by_date.keys())
    if not dates_with_data:
        _LOGGER.warning("No growth or yield data available for plant %s", plant_id)
        series = []
    else:
        # Establish date range for iteration
        min_date_str = min(dates_with_data)
        max_date_str = max(dates_with_data)
        try:
            min_date = datetime.fromisoformat(min_date_str).date()
        except Exception:
            min_date = (
                datetime.strptime(min_date_str, "%Y-%m-%d").date()
                if min_date_str
                else None
            )
        try:
            max_date = datetime.fromisoformat(max_date_str).date()
        except Exception:
            max_date = (
                datetime.strptime(max_date_str, "%Y-%m-%d").date()
                if max_date_str
                else None
            )

        series = []
        current_cumulative = 0.0
        date_iter = min_date
        while date_iter and date_iter <= max_date:
            date_str = date_iter.isoformat()
            has_yield = date_str in yield_by_date
            has_growth = date_str in growth_by_date
            if force or has_yield or has_growth:
                # Include this day if forced or if there's data on this day
                entry = {"date": date_str}
                # Add growth metric if available and not None
                if has_growth:
                    gm_val = growth_by_date.get(date_str)
                    if gm_val is not None:
                        # Round growth metric for readability if it's a float
                        if isinstance(gm_val, float):
                            gm_val = round(gm_val, 2)
                        entry["growth_metric"] = gm_val
                # Add yield for the day if present
                if has_yield:
                    y_val = yield_by_date.get(date_str, 0)
                    try:
                        y_val = float(y_val)
                    except Exception:
                        pass
                    # Round yield to two decimals (or leave as int if whole number)
                    y_val = round(y_val, 2)
                    entry["yield_quantity"] = y_val
                    current_cumulative += float(y_val)
                else:
                    # No yield event today; cumulative remains unchanged
                    current_cumulative += 0
                # Record cumulative yield up to this day
                entry["cumulative_yield"] = (
                    round(current_cumulative, 2)
                    if isinstance(current_cumulative, float)
                    else current_cumulative
                )
                series.append(entry)
            # Move to the next day
            date_iter += timedelta(days=1)

    # Ensure output directory exists
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{plant_id}_growth_yield.json"
    save_json(out_file, series)
    _LOGGER.info(
        "Exported growth & yield series for plant %s to %s", plant_id, out_file
    )
    return series
