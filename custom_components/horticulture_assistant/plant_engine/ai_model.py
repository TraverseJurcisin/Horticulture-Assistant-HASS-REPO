"""AI model interface for adjusting plant thresholds."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Protocol

import asyncio

from ..utils.ai_async import async_chat_completion

# === Configuration ===

USE_OPENAI = False  # Toggle between mock mode and API
OPENAI_MODEL = "gpt-4o"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)  # Stored in environment variable
try:
    OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
except (TypeError, ValueError):
    OPENAI_TEMPERATURE = 0.3


@dataclass(slots=True)
class AIModelConfig:
    """Runtime configuration for selecting the AI implementation."""

    use_openai: bool = USE_OPENAI
    model: str = OPENAI_MODEL
    api_key: str | None = OPENAI_API_KEY
    temperature: float = OPENAI_TEMPERATURE


class BaseAIModel(Protocol):
    """Protocol all AI implementations must follow."""

    def adjust_thresholds(self, data: Dict) -> Dict:
        """Return updated thresholds for ``data``."""
        raise NotImplementedError

    async def adjust_thresholds_async(self, data: Dict) -> Dict:
        """Asynchronously return updated thresholds for ``data``."""
        return self.adjust_thresholds(data)

# === Mock model ===

class MockAIModel:
    """Offline fallback / placeholder model."""

    def adjust_thresholds(self, data: Dict) -> Dict:
        old_thresholds = data.get("thresholds", {})
        lifecycle = data.get("lifecycle_stage", "")
        adjusted = {}

        for key, value in old_thresholds.items():
            if "leaf_" in key:
                if lifecycle == "fruiting":
                    adjusted[key] = round(value * 1.05, 2)
                elif lifecycle == "vegetative":
                    adjusted[key] = round(value * 0.95, 2)
                else:
                    adjusted[key] = value
            else:
                adjusted[key] = value

        return adjusted

    async def adjust_thresholds_async(self, data: Dict) -> Dict:
        """Asynchronous wrapper for :meth:`adjust_thresholds`."""
        return self.adjust_thresholds(data)


# === OpenAI API wrapper ===

class OpenAIModel:
    """Simple wrapper around the OpenAI API."""

    def __init__(self, config: AIModelConfig) -> None:
        self.config = config

    def _messages(self, data: Dict) -> list[dict[str, str]]:
        """Return formatted prompt messages for ``data``."""

        return [
            {
                "role": "system",
                "content": (
                    "You are an expert horticulturist AI. "
                    "You receive plant data including nutrient thresholds, lifecycle stage, and sensor data. "
                    "Return a dictionary of updated nutrient thresholds based on optimal plant performance."
                ),
            },
            {"role": "user", "content": f"Input data:\n{json.dumps(data, indent=2)}"},
        ]

    async def _request(self, data: Dict) -> Dict:
        if not self.config.api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment.")
        response = await async_chat_completion(
            self.config.api_key,
            self.config.model,
            self._messages(data),
            timeout=30,
        )
        text = response["choices"][0]["message"]["content"]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("OpenAI returned non-JSON output:\n" + text) from exc

    async def adjust_thresholds_async(self, data: Dict) -> Dict:
        """Asynchronously return updated thresholds via OpenAI."""

        return await self._request(data)

    def adjust_thresholds(self, data: Dict) -> Dict:
        """Return updated thresholds via OpenAI synchronously."""

        return asyncio.run(self._request(data))


# === Public Interface ===

def get_model(config: AIModelConfig | None = None) -> BaseAIModel:
    """Return an AI model instance based on ``config``."""

    cfg = config or AIModelConfig()
    return OpenAIModel(cfg) if cfg.use_openai else MockAIModel()


def analyze(data: Dict, config: AIModelConfig | None = None) -> Dict:
    """Return updated thresholds using the configured AI model."""

    model = get_model(config)
    return model.adjust_thresholds(data)


async def analyze_async(data: Dict, config: AIModelConfig | None = None) -> Dict:
    """Asynchronously return updated thresholds using the configured AI model."""

    model = get_model(config)
    return await model.adjust_thresholds_async(data)
