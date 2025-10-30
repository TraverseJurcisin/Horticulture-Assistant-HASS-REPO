import asyncio
import importlib
import importlib.util
import logging
import os
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.horticulture_assistant.ai_client import clear_ai_cache

pytest.importorskip("homeassistant.exceptions")

_BASE_DIR = Path(__file__).resolve().parents[1]
_PACKAGE_DIR = _BASE_DIR / "custom_components" / "horticulture_assistant"
_CLOUDSYNC_DIR = _PACKAGE_DIR / "cloudsync"

if "custom_components" not in sys.modules:
    cc_pkg = types.ModuleType("custom_components")
    cc_pkg.__path__ = [str((_BASE_DIR / "custom_components").resolve())]
    sys.modules["custom_components"] = cc_pkg

ha_pkg = sys.modules.setdefault(
    "custom_components.horticulture_assistant",
    types.ModuleType("custom_components.horticulture_assistant"),
)
ha_pkg.__path__ = [str(_PACKAGE_DIR.resolve())]

cloudsync_spec = importlib.util.spec_from_file_location(
    "custom_components.horticulture_assistant.cloudsync",
    _CLOUDSYNC_DIR / "__init__.py",
    submodule_search_locations=[str(_CLOUDSYNC_DIR.resolve())],
)
if cloudsync_spec is None or cloudsync_spec.loader is None:  # pragma: no cover - defensive
    raise ImportError("Unable to load cloudsync package")
cloudsync_module = importlib.util.module_from_spec(cloudsync_spec)
cloudsync_spec.loader.exec_module(cloudsync_module)
sys.modules["custom_components.horticulture_assistant.cloudsync"] = cloudsync_module
ha_pkg.cloudsync = cloudsync_module

EdgeSyncStore = cloudsync_module.EdgeSyncStore
import custom_components.horticulture_assistant.resolver as resolver_module  # noqa: E402
from custom_components.horticulture_assistant.config_flow import OptionsFlow  # noqa: E402
from custom_components.horticulture_assistant.const import DOMAIN, OPB_FIELD_MAP  # noqa: E402
from custom_components.horticulture_assistant.profile.schema import (  # noqa: E402
    BioProfile,
    FieldAnnotation,
    ResolvedTarget,
)
from custom_components.horticulture_assistant.profile.utils import (  # noqa: E402
    link_species_and_cultivars,
)
from custom_components.horticulture_assistant.resolver import (  # noqa: E402
    PreferenceResolver,
    generate_profile,
)

try:
    UTC = datetime.UTC  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover
    UTC = timezone.utc  # noqa: UP017


class DummyEntry:
    def __init__(self, options, entry_id="test_entry"):
        self.options = options
        self.entry_id = entry_id


class DummyRegistry:
    def __init__(self, profiles: list[BioProfile]):
        self._profiles = {profile.profile_id: profile for profile in profiles}
        link_species_and_cultivars(self._profiles.values())
        for profile in self._profiles.values():
            profile.refresh_sections()

    def get_profile(self, profile_id: str) -> BioProfile | None:
        return self._profiles.get(profile_id)

    def list_profiles(self) -> list[BioProfile]:
        return list(self._profiles.values())

    def iter_profiles(self) -> list[BioProfile]:
        return self.list_profiles()


def make_hass():
    tmpdir = tempfile.mkdtemp()
    loop = asyncio.get_event_loop()

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
        helpers=types.SimpleNamespace(aiohttp_client=types.SimpleNamespace(async_get_clientsession=MagicMock())),
        data={},
        state=None,
        async_create_task=async_create_task,
        async_add_executor_job=async_add_executor_job,
        loop=loop,
    )


@pytest.mark.asyncio
async def test_manual_source_applies_immediately():
    hass = make_hass()
    entry = DummyEntry({"profiles": {"p1": {"sources": {"temp_c_min": {"mode": "manual", "value": 1.0}}}}})
    await PreferenceResolver(hass).resolve_profile(entry, "p1")
    assert entry.options["profiles"]["p1"]["thresholds"]["temp_c_min"] == 1.0
    target = entry.options["profiles"]["p1"]["resolved_targets"]["temp_c_min"]
    assert target["value"] == 1.0
    assert target["annotation"]["source_type"] == "manual"
    local = entry.options["profiles"]["p1"]["local"]
    assert local["resolver_state"]["resolved_keys"] == ["temp_c_min"]
    assert local["citations"][0]["source"] == "manual"
    assert local["metadata"]["citation_map"]["temp_c_min"]["mode"] == "manual"


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
    assert entry.options["profiles"]["b"]["resolved_targets"]["temp_c_min"]["value"] == 2.0
    local = entry.options["profiles"]["b"]["local"]
    assert "temp_c_min" in local["metadata"]["citation_map"]
    assert local["citations"][0]["source"] == "clone"


@pytest.mark.asyncio
async def test_inheritance_fallback_uses_species_profile():
    hass = make_hass()
    species = BioProfile(
        profile_id="species.parent",
        display_name="Parent Species",
        profile_type="species",
    )
    species.resolved_targets["temp_c_min"] = ResolvedTarget(
        value=11.5,
        annotation=FieldAnnotation(
            source_type="manual",
            source_ref=["species.parent"],
            method="manual",
        ),
        citations=[],
    )
    species.refresh_sections()

    cultivar = BioProfile(
        profile_id="cultivar.child",
        display_name="Child Cultivar",
        profile_type="cultivar",
        species="species.parent",
    )
    cultivar.parents = ["species.parent"]

    registry = DummyRegistry([species, cultivar])
    entry = DummyEntry({"profiles": {"cultivar.child": {"name": "Child"}}})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"profile_registry": registry}

    await PreferenceResolver(hass).resolve_profile(entry, "cultivar.child")

    profile_options = entry.options["profiles"]["cultivar.child"]
    assert profile_options["thresholds"]["temp_c_min"] == 11.5
    target = profile_options["resolved_targets"]["temp_c_min"]
    assert target["value"] == 11.5
    assert target["annotation"]["source_type"] == "inheritance"
    extras = target["annotation"]["extras"]
    assert extras["source_profile_id"] == "species.parent"
    assert extras["inheritance_depth"] == 1
    assert extras["inheritance_chain"] == ["cultivar.child", "species.parent"]
    assert target["annotation"]["overlay_source_type"] == "manual"

    local = profile_options["local"]
    assert local["metadata"]["citation_map"]["temp_c_min"]["mode"] == "inheritance"
    assert any(cit["source"] == "inheritance" for cit in local["citations"])

    lineage = profile_options.get("lineage", [])
    assert lineage and lineage[0]["profile_id"] == "cultivar.child"
    assert any(item["profile_id"] == "species.parent" for item in lineage)


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
    annotation = entry.options["profiles"]["p1"]["resolved_targets"]["temp_c_min"]["annotation"]
    assert annotation["source_type"] == "openplantbook"
    local = entry.options["profiles"]["p1"]["local"]
    assert local["citations"][0]["source"] == "openplantbook"
    assert local["resolver_state"]["sources"]["temp_c_min"]["mode"] == "opb"


@pytest.mark.asyncio
async def test_ai_source_respects_ttl_and_caches():
    hass = make_hass()
    entry = DummyEntry({"profiles": {"p1": {"sources": {"temp_c_max": {"mode": "ai", "ai": {"ttl_hours": 720}}}}}})
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
    assert entry.options["profiles"]["p1"]["resolved_targets"]["temp_c_max"]["value"] == 4.0
    local = entry.options["profiles"]["p1"]["local"]
    assert local["citations"][0]["source"] == "ai"
    assert "temp_c_max" in local["metadata"]["citation_map"]


@pytest.mark.asyncio
async def test_ai_source_handles_invalid_ttl_gracefully():
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "invalid_ttl_profile": {"sources": {"temp_c_max": {"mode": "ai", "ai": {"ttl_hours": "not-a-number"}}}}
            }
        }
    )
    mock = AsyncMock(return_value=(5.5, 0.8, "note", []))
    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        mock,
    ):
        await PreferenceResolver(hass).resolve_profile(entry, "invalid_ttl_profile")

    assert mock.call_count == 1
    profile_options = entry.options["profiles"]["invalid_ttl_profile"]
    assert profile_options["thresholds"]["temp_c_max"] == 5.5
    assert profile_options["resolved_targets"]["temp_c_max"]["value"] == 5.5


@pytest.mark.asyncio
async def test_ai_source_handles_invalid_last_run_timestamp():
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "p1": {
                    "sources": {
                        "temp_c_max": {
                            "mode": "ai",
                            "ai": {
                                "ttl_hours": 720,
                                "last_run": "not-a-timestamp",
                            },
                        }
                    }
                }
            }
        }
    )
    mock = AsyncMock(return_value=(6.2, 0.9, "note", ["http://example"]))
    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        mock,
    ):
        clear_ai_cache()
        await PreferenceResolver(hass).resolve_profile(entry, "p1")

    assert mock.call_count == 1
    profile_options = entry.options["profiles"]["p1"]
    assert profile_options["thresholds"]["temp_c_max"] == 6.2
    resolved = profile_options["resolved_targets"]["temp_c_max"]
    assert resolved["value"] == 6.2


@pytest.mark.asyncio
async def test_ai_source_refreshes_when_cached_value_missing():
    hass = make_hass()
    recent = datetime.now(UTC).isoformat()
    entry = DummyEntry(
        {
            "profiles": {
                "p1": {
                    "sources": {
                        "temp_c_max": {
                            "mode": "ai",
                            "ai": {"ttl_hours": 720, "last_run": recent},
                        }
                    },
                    "thresholds": {},
                }
            }
        }
    )
    mock = AsyncMock(return_value=(7.5, 0.9, "note", []))
    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        mock,
    ):
        clear_ai_cache()
        await PreferenceResolver(hass).resolve_profile(entry, "p1")

    assert mock.call_count == 1
    profile_options = entry.options["profiles"]["p1"]
    assert profile_options["thresholds"]["temp_c_max"] == 7.5
    resolved = profile_options["resolved_targets"]["temp_c_max"]
    assert resolved["value"] == 7.5


@pytest.mark.asyncio
async def test_ai_source_preserves_fractional_ttl():
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "p1": {
                    "sources": {
                        "temp_c_max": {"mode": "ai", "ai": {"ttl_hours": 0.5}},
                    }
                }
            }
        }
    )
    mock = AsyncMock(return_value=(6.0, 0.85, "note", []))
    with patch(
        "custom_components.horticulture_assistant.ai_client.AIClient.generate_setpoint",
        mock,
    ):
        clear_ai_cache()
        resolver = PreferenceResolver(hass)
        await resolver.resolve_profile(entry, "p1")
        await resolver.resolve_profile(entry, "p1")

    assert mock.call_count == 1
    ai_meta = entry.options["profiles"]["p1"]["sources"]["temp_c_max"]["ai"]
    assert ai_meta["ttl_hours"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_resolver_uses_cloud_overlay_when_available():
    hass = make_hass()
    entry = DummyEntry(
        {
            "profiles": {
                "p1": {
                    "name": "Tophat Local",
                    "sources": {"temp_c_min": {"mode": "manual", "value": 5.0}},
                    "general": {"name": "Tophat Local"},
                }
            }
        }
    )

    store = EdgeSyncStore(":memory:")
    store.update_cloud_cache(
        "profile",
        "p1",
        "tenant-1",
        {
            "profile_id": "p1",
            "profile_type": "line",
            "parents": ["species-1"],
            "identity": {"name": "Tophat Cloud"},
            "taxonomy": {"species": "Vaccinium tophat"},
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.9}}},
        },
    )
    store.update_cloud_cache(
        "profile",
        "species-1",
        "tenant-1",
        {
            "profile_id": "species-1",
            "profile_type": "species",
            "parents": [],
            "curated_targets": {"targets": {"vpd": {"vegetative": 0.85}}},
        },
    )
    store.update_cloud_cache(
        "computed",
        "species-1",
        "tenant-1",
        {
            "computed_at": "2025-10-19T00:00:00Z",
            "payload": {"targets": {"vpd": {"vegetative": 0.8}}},
        },
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "cloud_sync_manager": types.SimpleNamespace(
            store=store,
            config=types.SimpleNamespace(tenant_id="tenant-1"),
        )
    }

    await PreferenceResolver(hass).resolve_profile(entry, "p1")

    profile_options = entry.options["profiles"]["p1"]
    assert profile_options["thresholds"]["temp_c_min"] == 5.0
    assert profile_options["library"]["curated_targets"]["targets"]["vpd"]["vegetative"] == 0.9
    assert profile_options["identity"]["name"] == "Tophat Cloud"
    computed = profile_options["computed_stats"]
    assert computed and computed[0]["payload"]["targets"]["vpd"]["vegetative"] == 0.8
    resolved = profile_options["resolved_targets"]["targets.vpd.vegetative"]
    assert resolved["value"] == 0.9
    assert resolved["annotation"]["overlay"] == 0.8
    sections = profile_options["sections"]
    assert sections["library"]["profile_id"] == "p1"
    assert sections["resolved"]["thresholds"]["temp_c_min"] == 5.0
    assert sections["resolved"]["resolved_targets"]["targets.vpd.vegetative"]["value"] == 0.9
    assert sections["computed"]["snapshots"][0]["payload"]["targets"]["vpd"]["vegetative"] == 0.8
    lineage = profile_options.get("lineage", [])
    assert lineage and lineage[0]["profile_id"] == "p1"


@pytest.mark.asyncio
async def test_inheritance_failure_logs_warning(hass, caplog):
    hass = make_hass()
    lonely = BioProfile(profile_id="p1", display_name="Lonely")
    registry = DummyRegistry([lonely])
    entry = DummyEntry({"profiles": {"p1": {"name": "Lonely"}}})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"profile_registry": registry}

    with caplog.at_level(logging.WARNING):
        await PreferenceResolver(hass).resolve_profile(entry, "p1")

    assert any("Inheritance lookup" in record.message and "p1" in record.message for record in caplog.records)


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
    assert prof["resolved_targets"]["temp_c_min"]["annotation"]["source_type"] == "ai"
    local = prof["local"]
    assert any(cit["source"] == "ai" for cit in local["citations"])


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
    assert prof["citations"]["temp_c_min"]["mode"] == "openplantbook"
    assert prof["resolved_targets"]["temp_c_min"]["annotation"]["source_type"] == "openplantbook"
    local = prof["local"]
    assert local["resolver_state"]["sources"]["temp_c_min"]["mode"] == "opb"


@pytest.mark.asyncio
async def test_resolve_profile_updates_entry_options_when_update_entry_noop(monkeypatch):
    hass = types.SimpleNamespace(
        config_entries=types.SimpleNamespace(async_update_entry=lambda *_args, **_kwargs: None),
        data={},
    )
    entry = DummyEntry({"profiles": {"p1": {"name": "Plant"}}})

    monkeypatch.setattr(resolver_module, "VARIABLE_SPECS", [("temp_c_min",)])

    def fake_profile(_profile_id, _payload, *, display_name=None):
        return BioProfile(profile_id="p1", display_name=display_name or "Plant")

    monkeypatch.setattr(resolver_module, "options_profile_to_dataclass", fake_profile)
    monkeypatch.setattr(
        resolver_module.PreferenceResolver,
        "_profile_registry",
        lambda self, _entry: None,
    )
    monkeypatch.setattr(
        resolver_module.PreferenceResolver,
        "_overlay_cloud_profile",
        lambda self, *_args, **_kwargs: None,
    )

    async def fake_resolve(self, _entry, _profile_id, key, _src, thresholds, _options):
        thresholds[key] = 42.0
        return ResolvedTarget(
            value=42.0,
            annotation=FieldAnnotation(source_type="manual", method="manual"),
            citations=[],
        )

    monkeypatch.setattr(
        resolver_module.PreferenceResolver,
        "_resolve_variable",
        fake_resolve,
    )

    resolver = PreferenceResolver(hass)
    await resolver.resolve_profile(entry, "p1")

    updated = entry.options["profiles"]["p1"]
    assert updated["thresholds"]["temp_c_min"] == 42.0
    assert updated["resolved_targets"]["temp_c_min"]["value"] == 42.0


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
    profile_options = entry.options["profiles"]["p1"]
    resolved_targets = profile_options.get("resolved_targets", {})
    assert "resolved_targets" not in profile_options or "temp_c_min" not in resolved_targets


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
