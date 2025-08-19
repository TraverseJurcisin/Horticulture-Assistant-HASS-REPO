"""Asynchronous helpers for AI model calls.

This module provides a non-blocking wrapper around the OpenAI Chat
Completions endpoint.  It exposes :func:`async_chat_completion` which can be
awaited, supports configurable timeouts and plays nicely with task
cancellation.
"""

from __future__ import annotations

import asyncio
from typing import Any, Iterable

import aiohttp

__all__ = ["async_chat_completion"]


async def async_chat_completion(
    api_key: str,
    model: str,
    messages: Iterable[dict[str, Any]],
    *,
    timeout: float = 15.0,
    base_url: str = "https://api.openai.com/v1",
    session: aiohttp.ClientSession | None = None,
) -> dict[str, Any]:
    """Fetch a chat completion from OpenAI asynchronously.

    Parameters
    ----------
    api_key:
        API key used for authentication.
    model:
        Chat model to invoke.
    messages:
        Sequence of chat messages as dictionaries.
    timeout:
        Maximum number of seconds to wait for the HTTP request.  A
        :class:`asyncio.TimeoutError` is raised on timeout which also allows
        cooperative cancellation.
    base_url:
        Base URL for the OpenAI API.  Defaults to the public endpoint.
    session:
        Optional :class:`aiohttp.ClientSession` to use.  If omitted a temporary
        session is created and closed automatically.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "messages": list(messages)}
    own_session = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with asyncio.timeout(timeout):
            async with session.post(
                f"{base_url}/chat/completions", headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
    finally:
        if own_session:
            await session.close()
