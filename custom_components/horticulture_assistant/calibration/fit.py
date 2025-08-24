from __future__ import annotations

import numpy as np


def _r2_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    rmse = float(np.sqrt(ss_res / max(1, len(y_true))))
    return r2, rmse


def fit_linear(lux: np.ndarray, ppfd: np.ndarray) -> tuple[list[float], float, float]:
    A = np.vstack([lux, np.ones_like(lux)]).T
    a, b = np.linalg.lstsq(A, ppfd, rcond=None)[0]
    pred = a * lux + b
    r2, rmse = _r2_rmse(ppfd, pred)
    return [float(a), float(b)], r2, rmse


def fit_quadratic(lux: np.ndarray, ppfd: np.ndarray) -> tuple[list[float], float, float]:
    coeffs = np.polyfit(lux, ppfd, 2)
    pred = np.polyval(coeffs, lux)
    r2, rmse = _r2_rmse(ppfd, pred)
    return [float(coeffs[0]), float(coeffs[1]), float(coeffs[2])], r2, rmse


def fit_power(lux: np.ndarray, ppfd: np.ndarray) -> tuple[list[float], float, float]:
    lux_pos = np.clip(lux, 1e-6, None)
    y = np.log(ppfd)
    X = np.log(lux_pos)
    b, loga = np.polyfit(X, y, 1)
    a = np.exp(loga)
    pred = a * (lux_pos**b)
    r2, rmse = _r2_rmse(ppfd, pred)
    return [float(a), float(b)], r2, rmse


def eval_model(model: str, coeffs: list[float], lux: np.ndarray) -> np.ndarray:
    if model == "linear":
        a, b = coeffs
        return a * lux + b
    if model == "quadratic":
        a, b, c = coeffs
        return a * (lux**2) + b * lux + c
    if model == "power":
        a, b = coeffs
        lux_pos = np.clip(lux, 1e-6, None)
        return a * (lux_pos**b)
    raise ValueError(f"Unknown model: {model}")
