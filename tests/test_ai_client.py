import importlib.util
import sys
import types
from collections.abc import Mapping
from datetime import datetime as dt
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

spec = importlib.util.spec_from_file_location(
    "ai_utils",
    Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant" / "ai_utils.py",
)
ai_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_utils)
extract_numbers = ai_utils.extract_numbers

# Provide package stubs so ai_client can perform relative imports without executing the full integration.
root_pkg = types.ModuleType("custom_components")
root_pkg.__path__ = []
pkg = types.ModuleType("custom_components.horticulture_assistant")
pkg.__path__ = [str(Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant")]
root_pkg.horticulture_assistant = pkg
sys.modules["custom_components"] = root_pkg
sys.modules["custom_components.horticulture_assistant"] = pkg
sys.modules["custom_components.horticulture_assistant.ai_utils"] = ai_utils

ai_spec = importlib.util.spec_from_file_location(
    "ai_client",
    Path(__file__).resolve().parent.parent / "custom_components" / "horticulture_assistant" / "ai_client.py",
)
ai_client_mod = importlib.util.module_from_spec(ai_spec)
ai_client_mod.__package__ = "custom_components.horticulture_assistant"
ai_spec.loader.exec_module(ai_client_mod)
AIClient = ai_client_mod.AIClient
async_recommend_variable = ai_client_mod.async_recommend_variable
_AI_CACHE = ai_client_mod._AI_CACHE
_normalise_cache_value = ai_client_mod._normalise_cache_value


def test_extract_numbers_filters_duplicates_and_range():
    text = "Values 20C, 30C, 20, 5000, -400, 25"
    assert extract_numbers(text) == [20.0, 25.0, 30.0]


def test_normalise_cache_value_handles_nested_structures():
    data = {"a": [1, 2, {"b": {"c": 3}}], "d": {1, 2}}
    normalised = _normalise_cache_value(data)

    # The normalised form should be hashable and stable across invocations.
    assert isinstance(normalised, tuple)
    assert normalised == _normalise_cache_value(data)


def test_normalise_cache_value_stabilises_sets_with_varying_iteration():
    class FlakySet(set):
        """Set subclass that flips iteration order on each call."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._toggle = False

        def __iter__(self):
            self._toggle = not self._toggle
            items = list(super().__iter__())
            if self._toggle:
                items.reverse()
            return iter(items)

    flaky = FlakySet({"a", "b", "c"})
    first = _normalise_cache_value(flaky)
    second = _normalise_cache_value(flaky)
    assert first == second


@pytest.mark.asyncio
async def test_async_recommend_variable_caches_result(monkeypatch, hass):
    _AI_CACHE.clear()
    mock = AsyncMock(return_value=(1.0, 0.5, "summary", []))
    monkeypatch.setattr(AIClient, "generate_setpoint", mock)
    first = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    second = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    assert first == second
    assert mock.call_count == 1


@pytest.mark.asyncio
async def test_async_recommend_variable_cache_accounts_for_context(monkeypatch, hass):
    _AI_CACHE.clear()
    mock = AsyncMock(side_effect=[(1.0, 0.5, "openai", []), (2.0, 0.6, "anthropic", [])])
    monkeypatch.setattr(AIClient, "generate_setpoint", mock)

    await async_recommend_variable(
        hass,
        key="temp",
        plant_id="p1",
        ttl_hours=1,
        provider="openai",
        model="gpt-4o-mini",
    )
    await async_recommend_variable(
        hass,
        key="temp",
        plant_id="p1",
        ttl_hours=1,
        provider="anthropic",
        model="claude-3-sonnet",
    )

    assert mock.call_count == 2


@pytest.mark.asyncio
async def test_generate_setpoint_handles_search_results(monkeypatch, hass):
    hass.secrets = {}
    hass.data.setdefault("secrets", {})

    class DummySearchResponse:
        def __init__(self, payload):
            self.status = 200
            self._payload = payload

        async def json(self):
            return self._payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummySession:
        def __init__(self):
            self.get_calls = 0

        def get(self, url, timeout):
            self.get_calls += 1
            assert "search" in url
            return DummySearchResponse({"items": [{"link": "https://doc.example/guide"}]})

        def post(self, *args, **kwargs):
            raise AssertionError("LLM refinement should not be invoked in test")

    dummy_session = DummySession()
    monkeypatch.setattr(ai_client_mod, "async_get_clientsession", lambda _hass: dummy_session)
    monkeypatch.setattr(ai_client_mod, "_fetch_text", AsyncMock(return_value="value 10 value 20"))

    client = AIClient(hass, provider="openai", model="gpt-4o")
    value, confidence, summary, links = await client.generate_setpoint(
        {
            "key": "temperature",
            "plant_id": "plant-1",
            "search_endpoint": "https://example.test/search",
            "search_key": "secret",
        }
    )

    assert dummy_session.get_calls == 1
    assert value == pytest.approx(15.0)
    assert confidence == 0.5
    assert summary == "Heuristic synthesis (no LLM)"
    assert links == ["https://doc.example/guide"]


@pytest.mark.asyncio
async def test_async_recommend_variable_normalises_blank_provider(monkeypatch, hass):
    _AI_CACHE.clear()

    captured: dict[str, str] = {}

    class DummyClient:
        def __init__(self, _hass, provider, model):
            captured["provider"] = provider
            captured["model"] = model

        async def generate_setpoint(self, context):
            return 2.5, 0.4, "summary", context.get("links", [])

    monkeypatch.setattr(ai_client_mod, "AIClient", DummyClient)

    result = await async_recommend_variable(
        hass,
        key="humidity",
        plant_id="plant-1",
        provider="  ",
        model="",
    )

    assert captured["provider"] == "openai"
    assert captured["model"] == "gpt-4o-mini"
    assert result["value"] == 2.5


@pytest.mark.asyncio
async def test_async_recommend_variable_honours_per_call_ttl(monkeypatch, hass):
    _AI_CACHE.clear()

    class FixedDateTime(dt):
        current = dt(2024, 1, 1, tzinfo=ai_client_mod.UTC)

        @classmethod
        def now(cls, tz=None):
            if tz is not None:
                return cls.current.astimezone(tz)
            return cls.current

        @classmethod
        def advance(cls, **kwargs):
            cls.current = cls.current + timedelta(**kwargs)

    monkeypatch.setattr(ai_client_mod, "datetime", FixedDateTime)

    mock = AsyncMock(side_effect=[(1.0, 0.5, "first", []), (2.0, 0.6, "second", [])])
    monkeypatch.setattr(AIClient, "generate_setpoint", mock)

    first = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    assert first["value"] == 1.0
    assert mock.call_count == 1

    FixedDateTime.advance(minutes=30)
    second = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    assert second == first
    assert second is not first
    assert mock.call_count == 1

    FixedDateTime.advance(hours=2)
    third = await async_recommend_variable(hass, key="temp", plant_id="p1", ttl_hours=1)
    assert third["value"] == 2.0
    assert mock.call_count == 2


@pytest.mark.asyncio
async def test_async_recommend_variable_returns_copy_of_cached_result(monkeypatch, hass):
    _AI_CACHE.clear()
    monkeypatch.setattr(AIClient, "generate_setpoint", AsyncMock(return_value=(3.0, 0.9, "summary", [])))

    result = await async_recommend_variable(hass, key="ec", plant_id="plant-1", ttl_hours=10)
    result["value"] = 99.0

    cached = await async_recommend_variable(hass, key="ec", plant_id="plant-1", ttl_hours=10)

    assert cached["value"] == 3.0
    assert cached is not result


@pytest.mark.asyncio
async def test_async_recommend_variable_cached_links_are_isolated(monkeypatch, hass):
    _AI_CACHE.clear()
    monkeypatch.setattr(
        AIClient,
        "generate_setpoint",
        AsyncMock(return_value=(5.0, 0.8, "summary", ["https://example.test/one"])),
    )

    first = await async_recommend_variable(hass, key="ph", plant_id="plant-1", ttl_hours=10)
    first["links"].append("https://bad.example/extra")

    second = await async_recommend_variable(hass, key="ph", plant_id="plant-1", ttl_hours=10)

    assert second["links"] == ["https://example.test/one"]
    assert second["links"] is not first["links"]


def test_get_openai_key_prefers_hass_secrets(hass):
    hass.secrets = {"OPENAI_API_KEY": "attr-secret"}
    hass.data.setdefault("secrets", {})["OPENAI_API_KEY"] = "data-secret"

    client = AIClient(hass, provider="openai", model="gpt-4o")

    assert client._get_openai_key() == "attr-secret"


def test_get_openai_key_supports_mapping_based_secrets(hass):
    class SecretsMapping(Mapping[str, str]):
        def __init__(self, data: dict[str, str]) -> None:
            self._data = data

        def __getitem__(self, key: str) -> str:
            return self._data[key]

        def __iter__(self):
            return iter(self._data)

        def __len__(self) -> int:
            return len(self._data)

        def get(self, key: str, default: str | None = None) -> str | None:
            return self._data.get(key, default)

    hass.secrets = SecretsMapping({"OPENAI_API_KEY": "  mapped-secret  "})
    hass.data.setdefault("secrets", {})

    client = AIClient(hass, provider="openai", model="gpt-4o")

    assert client._get_openai_key() == "mapped-secret"


def test_get_openai_key_falls_back_to_hass_data(hass):
    hass.secrets = None
    hass.data.setdefault("secrets", {})["OPENAI_API_KEY"] = "data-secret"

    client = AIClient(hass, provider="openai", model="gpt-4o")

    assert client._get_openai_key() == "data-secret"
