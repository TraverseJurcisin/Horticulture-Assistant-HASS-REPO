"""Compatibility helpers for optional :mod:`aiohttp` dependency."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ClientError",
    "ClientResponseError",
    "ClientSession",
    "AIOHTTP_AVAILABLE",
]

try:  # pragma: no cover - exercised in Home Assistant runtime
    from aiohttp import ClientError, ClientResponseError, ClientSession
    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover - executed in tests/CLI
    AIOHTTP_AVAILABLE = False

    try:  # Prefer any stubbed versions provided by tests
        from aiohttp import ClientError as _ClientError  # type: ignore
    except Exception:  # pragma: no cover - fallback when module missing entirely
        _ClientError = Exception  # type: ignore[assignment]
    ClientError = _ClientError  # type: ignore[misc,assignment]

    try:
        from aiohttp import ClientResponseError as _ClientResponseError  # type: ignore
    except Exception:  # pragma: no cover - no stub available
        class ClientResponseError(ClientError):  # type: ignore[override]
            """Fallback error used when :mod:`aiohttp` is unavailable."""

            def __init__(self, *args: Any, status: int | None = None, **kwargs: Any) -> None:
                super().__init__(*args)
                self.status = status or 0
    else:
        if hasattr(_ClientResponseError, "status"):
            ClientResponseError = _ClientResponseError  # type: ignore[assignment]
        else:
            class ClientResponseError(_ClientResponseError):  # type: ignore[misc]
                """Wrap stubbed errors with a ``status`` attribute for compatibility."""

                def __init__(self, *args: Any, status: int | None = None, **kwargs: Any) -> None:
                    super().__init__(*args)
                    self.status = status or 0

    class ClientSession:  # type: ignore[misc]
        """Lightweight stub that raises when HTTP features are used without aiohttp."""

        closed = True

        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - simple guard
            raise RuntimeError("aiohttp is required for cloud sync features but is not installed")

        async def close(self) -> None:  # pragma: no cover - API compatibility
            return None
