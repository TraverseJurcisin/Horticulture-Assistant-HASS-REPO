import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock
import sys
import types

import pytest

spec = importlib.util.spec_from_file_location(
    "ai_utils", Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant" / "ai_utils.py"
)
ai_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_utils)
extract_numbers = ai_utils.extract_numbers

# Provide package stubs so ai_client can perform relative imports without executing the full integration.
root_pkg = types.ModuleType("custom_components")
root_pkg.__path__ = []
pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [
    str(Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant")
]
root_pkg.horticulture_assistant = pkg
sys.modules["custom_components"] = root_pkg
sys.modules["custom_components.horticulture_assistant"] = pkg
sys.modules["custom_components.horticulture_assistant.ai_utils"] = ai_utils

ai_spec = importlib.util.spec_from_file_location(
    "ai_client", Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant" / "ai_client.py"
)
ai_client_mod = importlib.util.module_from_spec(ai_spec)
ai_client_mod.__package__ = "custom_components.horticulture_assistant"
ai_spec.loader.exec_module(ai_client_mod)
AIClient = ai_client_mod.AIClient
async_recommend_variable = ai_client_mod.async_recommend_variable
_AI_CACHE = ai_client_mod._AI_CACHE


def test_extract_numbers_filters_duplicates_and_range():
    text = "Values 20C, 30C, 20, 5000, -400, 25"
    assert extract_numbers(text) == [20.0, 25.0, 30.0]


@pytest.mark.asyncio
async def test_async_recommend_variable_caches_result(monkeypatch, hass):
    _AI_CACHE.clear()
    mock = AsyncMock(return_value=(1.0, 0.5, "summary", []))
    monkeypatch.setattr(AIClient, "generate_setpoint", mock)
    first = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    second = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    assert first == second
    assert mock.call_count == 1
