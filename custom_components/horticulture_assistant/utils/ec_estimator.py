"""Utilities for estimating root zone electrical conductivity (EC).

This module provides a lightweight linear estimator that can be trained on historical data and later used to infer EC
values from recent sensor logs. The functions are intentionally dependency free so they can be executed during unit
tests without a Home Assistant install.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from pathlib import Path

import numpy as np

try:
    from homeassistant.core import HomeAssistant
except Exception:  # pragma: no cover - Home Assistant not installed in tests
    HomeAssistant = None  # type: ignore

from plant_engine.fertigation import estimate_solution_ec
from plant_engine.utils import load_dataset

from plant_engine import ec_manager

from .bio_profile_loader import load_profile_by_id
from .json_io import load_json, save_json
from .path_utils import data_path, plants_path

_LOGGER = logging.getLogger(__name__)

MODEL_FILE = Path(data_path(None, "ec_model.json"))
DEFAULT_DATA_FILE = "ec/ec_model_defaults.json"


def _model_path(plant_id: str | None = None, *, base_path: str | Path | None = None) -> Path:
    """Return the path to the EC model file."""
    if plant_id:
        return Path(base_path or plants_path(None)) / plant_id / "ec_model.json"
    return Path(base_path or MODEL_FILE)


def _float_or_none(val: object) -> float | None:
    """Return ``val`` cast to ``float`` or ``None`` on failure."""

    try:
        return float(val)
    except (TypeError, ValueError):
        return None


@dataclass
class ECEstimator:
    """Linear estimator for root zone EC using arbitrary features."""

    intercept: float
    coeffs: Mapping[str, float]

    def predict(
        self,
        features: Mapping[str, float],
        runoff_ec: float | None = None,
    ) -> float:
        est = self.intercept
        for name, coef in self.coeffs.items():
            est += coef * features.get(name, 0.0)
        if runoff_ec is not None:
            est = (est + float(runoff_ec)) / 2.0
        return round(est, 3)

    def as_dict(self) -> dict:
        return {"intercept": self.intercept, "coeffs": dict(self.coeffs)}


_default_data = load_dataset(DEFAULT_DATA_FILE)
_default_coeffs = _default_data.get("coeffs", {}) if isinstance(_default_data, Mapping) else {}
if not isinstance(_default_coeffs, Mapping):
    _default_coeffs = {}
DEFAULT_MODEL = ECEstimator(
    float(_default_data.get("intercept", 0.0)),
    {
        "moisture": 0.02,
        "temperature": 0.05,
        "irrigation_ml": 0.001,
        "solution_ec": 0.8,
        **{k: float(v) for k, v in _default_coeffs.items()},
    },
)


@dataclass(slots=True)
class ECFeatures:
    """Container for features used by :class:`ECEstimator`."""

    moisture: float
    temperature: float
    irrigation_ml: float
    solution_ec: float
    ambient_temp: float | None = None
    humidity: float | None = None
    target_ec: float | None = None
    nutrient_ec: float | None = None
    media_factor: float | None = None

    def asdict(self) -> MutableMapping[str, float]:
        data: MutableMapping[str, float] = {
            "moisture": self.moisture,
            "temperature": self.temperature,
            "irrigation_ml": self.irrigation_ml,
            "solution_ec": self.solution_ec,
        }
        optional = {
            "ambient_temp": self.ambient_temp,
            "humidity": self.humidity,
            "target_ec": self.target_ec,
            "nutrient_ec": self.nutrient_ec,
            "media_factor": self.media_factor,
        }
        for key, value in optional.items():
            if value is not None:
                data[key] = float(value)
        return data


@cache
def load_model(
    path: str | Path | None = None,
    *,
    plant_id: str | None = None,
    base_path: str | Path | None = None,
) -> ECEstimator:
    """Return an :class:`ECEstimator` from ``path`` or defaults.

    A cached instance is returned to avoid repeatedly reading from disk.
    Use :func:`clear_model_cache` to invalidate the cache.
    """
    model_path = Path(path) if path is not None else _model_path(plant_id, base_path=base_path)
    try:
        data = load_json(str(model_path))
        coeffs = data.get("coeffs", {})
        intercept = float(data.get("intercept", 0.0))
        if not isinstance(coeffs, Mapping):
            raise ValueError("invalid coeffs")
        return ECEstimator(intercept, {k: float(v) for k, v in coeffs.items()})
    except FileNotFoundError:
        _LOGGER.debug("EC model not found at %s, using defaults", model_path)
    except Exception as exc:  # pragma: no cover - logging only
        _LOGGER.warning("Failed to load EC model %s: %s", model_path, exc)
    return DEFAULT_MODEL


def save_model(
    model: ECEstimator,
    path: str | Path | None = None,
    *,
    plant_id: str | None = None,
    base_path: str | Path | None = None,
) -> None:
    """Persist ``model`` to ``path`` and refresh the cache."""
    out_path = Path(path) if path is not None else _model_path(plant_id, base_path=base_path)
    save_json(str(out_path), model.as_dict())
    load_model.cache_clear()


def estimate_ec_from_values(
    moisture: float,
    temperature: float,
    irrigation_ml: float,
    solution_ec: float,
    *,
    model: ECEstimator | None = None,
    runoff_ec: float | None = None,
    extra_features: Mapping[str, float] | None = None,
    plant_id: str | None = None,
    base_path: str | Path | None = None,
) -> float:
    """Estimate EC directly from raw feature values."""

    feat = ECFeatures(
        moisture=moisture,
        temperature=temperature,
        irrigation_ml=irrigation_ml,
        solution_ec=solution_ec,
    )
    if extra_features:
        for key, value in extra_features.items():
            setattr(feat, key, value)

    mdl = model or load_model(plant_id=plant_id, base_path=base_path)
    return mdl.predict(feat.asdict(), runoff_ec)


def log_runoff_ec(
    plant_id: str,
    ec_value: float,
    *,
    base_path: str | Path | None = None,
) -> None:
    """Append a runoff EC reading for ``plant_id``."""
    plant_dir = Path(base_path or plants_path(None)) / plant_id
    plant_dir.mkdir(parents=True, exist_ok=True)
    log_file = plant_dir / "runoff_ec_log.json"

    try:
        entries = load_json(str(log_file)) if log_file.exists() else []
    except Exception:
        entries = []

    entry = {"timestamp": datetime.now().isoformat(), "ec": float(ec_value)}
    entries.append(entry)
    try:
        save_json(str(log_file), entries)
    except Exception as exc:  # pragma: no cover - logging only
        _LOGGER.error("Failed to write runoff EC log for %s: %s", plant_id, exc)


def _latest_log_value(entries: Iterable[Mapping[str, object]], key: str) -> float | None:
    """Return the most recent numeric ``key`` value from log ``entries``."""
    for entry in reversed(list(entries)):
        val = _float_or_none(entry.get(key))
        if val is not None:
            return val
    return None


def _latest_sensor_value(
    entries: Iterable[Mapping[str, object]], names: Iterable[str]
) -> float | None:
    names_l = [n.lower() for n in names]
    for entry in reversed(list(entries)):
        stype = str(entry.get("sensor_type", "")).lower()
        if stype in names_l or any(n in stype for n in names_l):
            val = _float_or_none(entry.get("value"))
            if val is not None:
                return val
    return None


def _env_value(env: Mapping[str, object], names: Iterable[str]) -> float | None:
    for n in names:
        if n in env:
            val = _float_or_none(env[n])
            if val is not None:
                return val
    return None


def _load_recent_entries(log_path: Path, limit: int = 10) -> list[dict]:
    """Return up to ``limit`` records from ``log_path`` if it exists."""

    try:
        data = load_json(str(log_path))
        if isinstance(data, list):
            return data[-limit:]
    except Exception:
        pass
    return []


def estimate_ec(
    plant_id: str,
    hass: HomeAssistant | None = None,
    *,
    base_path: str | Path | None = None,
) -> float | None:
    """Estimate EC for ``plant_id`` using recent logs and profile data."""

    plant_dir = Path(base_path or plants_path(hass)) / plant_id
    sensor_log = _load_recent_entries(plant_dir / "sensor_reading_log.json")
    irrigation_log = _load_recent_entries(plant_dir / "irrigation_log.json")
    nutrient_log = _load_recent_entries(plant_dir / "nutrient_application_log.json")
    runoff_log = _load_recent_entries(plant_dir / "runoff_ec_log.json")

    profile = load_profile_by_id(plant_id, base_dir=base_path or plants_path(hass))
    general = profile.get("general", {}) if profile else {}
    latest_env = (
        general.get("latest_env", {}) if isinstance(general.get("latest_env"), Mapping) else {}
    )

    moisture = _latest_sensor_value(sensor_log, ["soil_moisture", "moisture"]) or _env_value(
        latest_env, ["soil_moisture", "moisture"]
    )
    temperature = _latest_sensor_value(
        sensor_log, ["soil_temperature", "root_temperature"]
    ) or _env_value(latest_env, ["soil_temperature", "root_temperature"])
    irrigation_ml = _latest_log_value(irrigation_log, "volume_applied_ml") or 0.0
    ambient_temp = _latest_sensor_value(
        sensor_log, ["air_temperature", "ambient_temperature", "temperature"]
    ) or _env_value(latest_env, ["air_temperature", "ambient_temperature", "temperature"])
    humidity = _latest_sensor_value(sensor_log, ["humidity", "relative_humidity"]) or _env_value(
        latest_env, ["humidity", "relative_humidity"]
    )

    solution_ec = _latest_log_value(nutrient_log, "solution_ec") or 0.0
    formulation = None
    for entry in reversed(nutrient_log):
        data = entry.get("nutrient_formulation")
        if isinstance(data, Mapping):
            formulation = data
            break
    nutrient_ec = estimate_solution_ec(formulation) if formulation else 0.0
    if solution_ec <= 0 and nutrient_ec > 0:
        solution_ec = nutrient_ec

    runoff_ec = _latest_log_value(runoff_log, "ec")

    plant_type = general.get("plant_type", "")
    stage = general.get("lifecycle_stage") or general.get("stage")
    target_ec = ec_manager.get_optimal_ec(plant_type, stage) if plant_type else None

    medium = (general.get("growth_medium") or general.get("soil_texture") or "").lower()
    media_factor = {"soil": 1.0, "coco": 1.2, "hydroponic": 1.5}.get(medium, 0.0)

    if moisture is None or temperature is None:
        _LOGGER.info("Insufficient sensor data for EC estimate of %s", plant_id)
        return None

    features = ECFeatures(
        moisture=moisture,
        temperature=temperature,
        irrigation_ml=irrigation_ml,
        solution_ec=solution_ec,
        ambient_temp=ambient_temp,
        humidity=humidity,
        target_ec=target_ec,
        nutrient_ec=nutrient_ec if nutrient_ec else None,
        media_factor=media_factor if media_factor else None,
    )

    model = load_model(plant_id=plant_id, base_path=base_path)
    return model.predict(features.asdict(), runoff_ec)


def train_ec_model(
    samples: Iterable[Mapping[str, float]],
    *,
    output_path: str | Path | None = None,
    plant_id: str | None = None,
    base_path: str | Path | None = None,
) -> ECEstimator:
    """Return a linear :class:`ECEstimator` trained from ``samples``.

    ``samples`` should contain feature values and an ``observed_ec`` field.
    The resulting model is written to ``output_path`` if provided.
    """

    feature_names: set[str] = set()
    for row in samples:
        feature_names.update(k for k in row if k != "observed_ec")
    if not feature_names:
        raise ValueError("No valid features for training")
    names = sorted(feature_names)

    X = []
    y = []
    for row in samples:
        try:
            vec = [1.0] + [float(row.get(n, 0.0)) for n in names]
            y.append(float(row["observed_ec"]))
            X.append(vec)
        except Exception as exc:
            _LOGGER.warning("Invalid sample row skipped: %s", exc)
    if not X:
        raise ValueError("No valid samples for training")

    coef, *_ = np.linalg.lstsq(np.array(X), np.array(y), rcond=None)
    coeffs = {name: coef[i + 1] for i, name in enumerate(names)}
    model = ECEstimator(intercept=coef[0], coeffs=coeffs)

    save_model(
        model,
        path=output_path,
        plant_id=plant_id,
        base_path=base_path,
    )
    return model


def clear_model_cache() -> None:
    """Clear any cached EC models."""

    load_model.cache_clear()
