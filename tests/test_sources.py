import os
import tempfile
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("homeassistant.exceptions")

from custom_components.horticulture_assistant.config_flow import OptionsFlow  # noqa: E402
from custom_components.horticulture_assistant.const import OPB_FIELD_MAP  # noqa: E402
from custom_components.horticulture_assistant.resolver import (  # noqa: E402
    PreferenceResolver,
    generate_profile,
)


class DummyEntry:
    def __init__(self, options):
        self.options = options


def make_hass():
    tmpdir = tempfile.mkdtemp()

    def update_entry(entry, *, options):
        entry.options = options

    def async_create_task(coro, *_args, **_kwargs):
        import asyncio

        return asyncio.create_task(coro)

    async def async_add_executor_job(func, *args):
        return func(*args)

    def config_path(*_args):
        return os.path.join(tmpdir, "test.json")

    return types.SimpleNamespace(
        config_entries=types.SimpleNamespace(async_update_entry=update_entry),
        config=types.SimpleNamespace(
            location_name="loc",
            units=types.SimpleNamespace(name="metric"),
            path=config_path,
            config_dir=tmpdir,
        ),
        helpers=types.SimpleNamespace(
            aiohttp_client=types.SimpleNamespace(async_get_clientsession=MagicMock())
        ),
        data={},
        state=None,
        async_create_task=async_create_task,
        async_add_executor_job=async_add_executor_job,
    )


@pytest.mark.asyncio
async def test_manual_source_applies_immediately():
    hass = make_hass()
    entry = DummyEntry(
        {"profiles": {"p1": {"sources": {"temp_c_min": {"mode": "manual", "value": 1.0}}}}}
    )
    await PreferenceResolver(hass).resolve_profile(entry, "p1")
    assert entry.options["profiles"]["p1"]["thresholds"]["temp_c_min"] == 1.0


@pytest.mark.asyncio
async def test_clone_source_copies_from_other_profile():
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "a": {"thresholds": {"temp_c_min": 2.0}},
                "b": {"sources": {"temp_c_min": {"mode": "clone", "copy_from": "a"}}},
            }
        }
    )
    await PreferenceResolver(hass).resolve_profile(entry, "b")
    assert entry.options["profiles"]["b"]["thresholds"]["temp_c_min"] == 2.0


@pytest.mark.asyncio
async def test_opb_source_maps_field():
    hass = make_hass()
    entry = DummyEntry(
        {
            "opb_token": "t",
            "profiles": {
                "p1": {
                    "sources": {
                        "temp_c_min": {
                            "mode": "opb",
                            "opb": {"species": "s", "field": "a.b"},
                        }
                    }
                }
            },
        }
    )
    with patch(
        "custom_components.horticulture_assistant.opb_client.OpenPlantbookClient.species_details",
        return_value={"a": {"b": 3}},
    ):
        await PreferenceResolver(hass).resolve_profile(entry, "p1")
    assert entry.options["profiles"]["p1"]["thresholds"]["temp_c_min"] == 3


@pytest.mark.asyncio
async def test_ai_source_respects_ttl_and_caches():
    hass = make_hass()
    entry = DummyEntry(
        {"profiles": {"p1": {"sources": {"temp_c_max": {"mode": "ai", "ai": {"ttl_hours": 720}}}}}}
    )
    mock = AsyncMock(return_value=(4.0, 0.9, "note", []))
    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        mock,
    ):
        r = PreferenceResolver(hass)
        await r.resolve_profile(entry, "p1")
        await r.resolve_profile(entry, "p1")
    assert mock.call_count == 1
    assert entry.options["profiles"]["p1"]["thresholds"]["temp_c_max"] == 4.0


@pytest.mark.asyncio
async def test_generate_profile_ai_sets_sources_and_citations():
    hass = make_hass()
    entry = DummyEntry({"profiles": {"p1": {"species": "s"}}})
    mock = AsyncMock(return_value=(5.0, 0.8, "n", []))
    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        mock,
    ):
        await generate_profile(hass, entry, "p1", "ai")
    prof = entry.options["profiles"]["p1"]
    assert prof["thresholds"]["temp_c_min"] == 5.0
    assert prof["citations"]["temp_c_min"]["mode"] == "ai"


@pytest.mark.asyncio
async def test_generate_profile_opb_sets_sources_and_citations():
    hass = make_hass()
    entry = DummyEntry({"opb_token": "t", "profiles": {"p1": {"species": {"slug": "sp"}}}})
    with patch(
        "custom_components.horticulture_assistant.opb_client.OpenPlantbookClient.species_details",
        AsyncMock(return_value={"temperature": {"min_c": 7.0}}),
    ):
        await generate_profile(hass, entry, "p1", "opb")
    prof = entry.options["profiles"]["p1"]
    field = OPB_FIELD_MAP.get("temp_c_min", "temp_c_min")
    assert prof["sources"]["temp_c_min"]["opb"]["field"] == field
    assert prof["thresholds"]["temp_c_min"] == 7.0
    assert prof["citations"]["temp_c_min"]["mode"] == "opb"


@pytest.mark.asyncio
async def test_options_flow_per_variable_steps():
    hass = make_hass()
    entry = DummyEntry({"profiles": {"p1": {"name": "Plant"}}})
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_profile()
    await flow.async_step_profile({"profile_id": "p1"})
    await flow.async_step_action({"action": "edit"})
    await flow.async_step_pick_variable()
    await flow.async_step_pick_variable({"variable": "temp_c_min"})
    await flow.async_step_pick_source({"mode": "manual"})
    await flow.async_step_src_manual({"value": 2.0})
    await flow.async_step_apply({"resolve_now": False})
    assert entry.options["profiles"]["p1"]["sources"]["temp_c_min"]["mode"] == "manual"


@pytest.mark.asyncio
async def test_options_flow_generate_profile():
    hass = make_hass()
    entry = DummyEntry({"profiles": {"p1": {"name": "Plant", "species": "s"}}})
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_profile()
    await flow.async_step_profile({"profile_id": "p1"})
    await flow.async_step_action({"action": "generate"})
    with patch(
        "custom_components.horticulture_assistant.resolver.PreferenceResolver.resolve_profile",
        AsyncMock(),
    ):
        await flow.async_step_generate({"mode": "ai"})
    assert entry.options["profiles"]["p1"]["sources"]["temp_c_min"]["mode"] == "ai"


@pytest.mark.asyncio
async def test_options_flow_generate_profile_clone():
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "p1": {"name": "Plant"},
                "src": {"name": "Source", "thresholds": {"temp_c_min": 7.0}},
            }
        }
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_profile()
    await flow.async_step_profile({"profile_id": "p1"})
    await flow.async_step_action({"action": "generate"})
    result = await flow.async_step_generate({"mode": "clone"})
    assert result["step_id"] == "generate_clone"
    with patch(
        "custom_components.horticulture_assistant.resolver.PreferenceResolver.resolve_profile",
        AsyncMock(),
    ):
        await flow.async_step_generate_clone({"copy_from": "src"})
    prof = entry.options["profiles"]["p1"]
    assert prof["thresholds"]["temp_c_min"] == 7.0
    assert prof["sources"]["temp_c_min"]["mode"] == "clone"
