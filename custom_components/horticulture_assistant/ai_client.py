from __future__ import annotations

import json
from typing import Any

import aiohttp


class AIClient:
    def __init__(self, hass, provider: str, model: str):
        self.hass = hass
        self.provider = provider
        self.model = model

    async def generate_setpoint(self, context: dict[str, Any]) -> tuple[float, float, str]:
        """
        Return (value, confidence, notes). Default implementation hits OpenAI if configured,
        else returns a conservative fallback and low confidence.
        """
        api_key = self._get_openai_key()
        if not api_key:
            return (0.0, 0.1, "AI disabled (no API key)")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        prompt = self._build_prompt(context)
        body = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": "You are an agronomy expert. Provide numeric setpoints only."},
                {"role": "user", "content": prompt},
            ],
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers=headers, data=json.dumps(body), timeout=30) as r:
                if r.status != 200:
                    return (0.0, 0.2, f"openai_error:{r.status}")
                data = await r.json()
                txt = data["choices"][0]["message"]["content"]
                val, conf = self._parse_response(txt)
                return (val, conf, "openai")

    def _build_prompt(self, ctx: dict) -> str:
        key = ctx.get("key")
        species = (ctx.get("species") or {}).get("slug") if isinstance(ctx.get("species"), dict) else ctx.get("species")
        loc = ctx.get("location")
        unit = ctx.get("unit_system")
        return (
            f"Determine an optimal setpoint for '{key}' for species '{species}'. "
            f"Assume indoor container horticulture, location '{loc}', unit system '{unit}'. "
            "Provide only a single numeric answer and a confidence in [0,1]."
        )

    def _parse_response(self, txt: str) -> tuple[float, float]:
        import re

        n = re.findall(r"[-+]?\d*\.?\d+", txt)
        if not n:
            return (0.0, 0.2)
        val = float(n[0])
        conf = float(n[1]) if len(n) > 1 else 0.5
        return (val, max(0.0, min(conf, 1.0)))

    def _get_openai_key(self) -> str | None:
        return getattr(self.hass.data.get("secrets", {}), "OPENAI_API_KEY", None) or None
