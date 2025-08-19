"""Shared helpers for resolving config directory paths."""

from __future__ import annotations

from pathlib import Path

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

    When ``hass`` is ``None`` the path is resolved relative to the current
    working directory.  Internally ``pathlib`` is used for clearer path
    handling and to avoid manual ``os.path`` manipulation.
    """

    if hass is not None:
        # Home Assistant already handles path joins via its helper.
        return hass.config.path(*parts)
    # ``Path()`` gives a relative path (``."``), matching previous
    # behaviour when Home Assistant is not available.
    return str(Path().joinpath(*parts))


def data_path(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``data`` in the configuration directory."""
    return config_path(hass, "data", *parts)


def plants_path(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``plants`` in the configuration directory."""
    return config_path(hass, "plants", *parts)


def ensure_dir(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a config directory path and create it if missing."""
    path = Path(config_path(hass, *parts))
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def ensure_data_dir(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``data`` and ensure the directory exists."""
    return ensure_dir(hass, "data", *parts)


def ensure_plants_dir(hass: HomeAssistant | None, *parts: str) -> str:
    """Return a path under ``plants`` and ensure the directory exists."""
    return ensure_dir(hass, "plants", *parts)
