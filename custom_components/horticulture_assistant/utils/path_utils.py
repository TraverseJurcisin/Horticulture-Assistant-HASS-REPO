"""Shared helpers for resolving config directory paths."""

from __future__ import annotations

import os

try:
    from homeassistant.core import HomeAssistant
except ImportError:  # pragma: no cover - Home Assistant not installed for tests
    HomeAssistant = None  # type: ignore

__all__ = [
    "config_path",
    "data_path",
    "plants_path",
    "ensure_dir",
    "ensure_data_dir",
    "ensure_plants_dir",
]


def config_path(hass: HomeAssistant | None, *parts: str) -> str:
    """Return an absolute path within the Home Assistant config directory.

    If ``hass`` is ``None`` the path is joined relative to the current
    working directory.
    """
    if hass is not None:
        return hass.config.path(*parts)
    return os.path.join(*parts)


def data_path(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``data`` in the configuration directory."""
    return config_path(hass, "data", *parts)


def plants_path(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``plants`` in the configuration directory."""
    return config_path(hass, "plants", *parts)


def ensure_dir(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a config directory path and create it if missing."""
    path = config_path(hass, *parts)
    os.makedirs(path, exist_ok=True)
    return path


def ensure_data_dir(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``data`` and ensure the directory exists."""
    return ensure_dir(hass, "data", *parts)


def ensure_plants_dir(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``plants`` and ensure the directory exists."""
    return ensure_dir(hass, "plants", *parts)

