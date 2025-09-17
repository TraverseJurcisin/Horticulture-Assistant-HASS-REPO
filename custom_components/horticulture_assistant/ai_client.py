from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .ai_utils import extract_numbers

UTC = getattr(datetime, "UTC", timezone.utc)  # type: ignore[attr-defined]  # noqa: UP017

_AI_CACHE: dict[tuple[str, str], tuple[dict[str, Any], datetime]] = {}


async def _fetch_text(session, url: str) -> str:
    """Fetch raw text content from a URL, stripping HTML tags."""
    try:
        async with session.get(url, timeout=15) as resp:
            if resp.status != 200:
                return ""
            txt = await resp.text()
    except Exception:
        return ""
    # naive HTML strip
    return re.sub(r"<[^>]+>", " ", txt)


class AIClient:
    """Lightweight AI helper with optional web sweep and OpenAI refinement."""

    def __init__(self, hass, provider: str, model: str) -> None:
        self.hass = hass
        self.provider = provider
        self.model = model

    async def generate_setpoint(
        self, context: dict[str, Any]
    ) -> tuple[float, float, str, list[str]]:
        """Return (value, confidence, summary, links)."""
        session = async_get_clientsession(self.hass)
        key = context.get("key")
        plant_id = context.get("plant_id")
        search_endpoint = context.get("search_endpoint")
        search_key = context.get("search_key")

        links: list[str] = []
        texts: list[str] = []

        # Optional web sweep
        if search_endpoint and search_key:
            try:
                query = str(
                    URL(search_endpoint).with_query(
                        q=f"{key} setpoint for plant {plant_id}",
                        api_key=search_key,
                    )
                )
                async with session.get(query, timeout=15) as resp:
                    if resp.status == 200:
                        js = await resp.json()
                        for item in (js.get("items") or js.get("results") or [])[:5]:
                            u = item.get("link") or item.get("url")
                            if u:
                                links.append(u)
            except Exception:
                pass
            if links:
                texts = await asyncio.gather(*[_fetch_text(session, u) for u in links])

        nums: list[float] = []
        for t in texts:
            nums.extend(extract_numbers(t)[:10])

        value: float | None = None
        if nums:
            nums.sort()
            k = max(0, int(len(nums) * 0.1))
            core = nums[k : len(nums) - k] or nums
            value = sum(core) / len(core)
        confidence = 0.5 if value is not None else 0.2

        api_key = self._get_openai_key()
        summary = "Heuristic synthesis (no LLM)"
        if api_key:
            prompt = (
                f"Given the candidate values {nums} for variable '{key}' in plant '{plant_id}', "
                "return a single numeric setpoint and one-sentence justification."
            )
            body = {
                "model": self.model,
                "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}],
            }
            try:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(body),
                    timeout=30,
                ) as resp:
                    if resp.status == 200:
                        jr = await resp.json()
                        txt = jr["choices"][0]["message"]["content"]
                        cand = extract_numbers(txt)
                        if cand:
                            value = cand[0]
                        summary = txt[:400]
                        confidence = 0.7
            except Exception:
                pass

        if value is None:
            value = 0.0
        return float(value), confidence, summary, links[:5]

    def _get_openai_key(self) -> str | None:
        secrets = self.hass.data.get("secrets", {})
        if isinstance(secrets, dict):
            return secrets.get("OPENAI_API_KEY")
        return None


async def async_recommend_variable(
    hass, key: str, plant_id: str, ttl_hours: int = 720, **kwargs
) -> dict[str, Any]:
    """Return AI recommendation for a variable with simple caching."""
    cache_key = (plant_id, key)
    now = datetime.now(UTC)
    cached = _AI_CACHE.get(cache_key)
    if cached and now < cached[1]:
        return cached[0]

    provider = kwargs.get("provider", "openai")
    model = kwargs.get("model", "gpt-4o-mini")
    client = AIClient(hass, provider, model)
    val, conf, summary, links = await client.generate_setpoint(
        {"key": key, "plant_id": plant_id, **kwargs}
    )
    result = {"value": val, "confidence": conf, "summary": summary, "links": links}
    _AI_CACHE[cache_key] = (result, now + timedelta(hours=ttl_hours))
    return result


def clear_ai_cache() -> None:
    """Clear cached AI recommendations."""
    _AI_CACHE.clear()
