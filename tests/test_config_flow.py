import asyncio
import importlib.util
import json
import logging
import shutil
import sys
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.helpers import selector as sel

from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "horticulture_assistant"
CONF_API_KEY = "api_key"

# Load const and config_flow modules without importing package __init__
PACKAGE = "custom_components.horticulture_assistant"
BASE_PATH = Path(__file__).resolve().parent.parent / "custom_components/horticulture_assistant"

if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(BASE_PATH)]
    sys.modules[PACKAGE] = pkg

const_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.const", BASE_PATH / "const.py")
const = importlib.util.module_from_spec(const_spec)
sys.modules[const_spec.name] = const
const_spec.loader.exec_module(const)
CONF_PLANT_NAME = const.CONF_PLANT_NAME
CONF_PLANT_ID = const.CONF_PLANT_ID
CONF_PLANT_TYPE = const.CONF_PLANT_TYPE
CONF_PROFILE_SCOPE = const.CONF_PROFILE_SCOPE
CONF_PROFILES = const.CONF_PROFILES
CONF_MOISTURE_SENSOR = const.CONF_MOISTURE_SENSOR
CONF_TEMPERATURE_SENSOR = const.CONF_TEMPERATURE_SENSOR
PROFILE_SCOPE_DEFAULT = const.PROFILE_SCOPE_DEFAULT
CONF_CLOUD_SYNC_ENABLED = const.CONF_CLOUD_SYNC_ENABLED
CONF_CLOUD_BASE_URL = const.CONF_CLOUD_BASE_URL
CONF_CLOUD_TENANT_ID = const.CONF_CLOUD_TENANT_ID
CONF_CLOUD_DEVICE_TOKEN = const.CONF_CLOUD_DEVICE_TOKEN
CONF_CLOUD_SYNC_INTERVAL = const.CONF_CLOUD_SYNC_INTERVAL
DEFAULT_CLOUD_SYNC_INTERVAL = const.DEFAULT_CLOUD_SYNC_INTERVAL

cfg_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.config_flow", BASE_PATH / "config_flow.py")
cfg = importlib.util.module_from_spec(cfg_spec)
sys.modules[cfg_spec.name] = cfg
cfg_spec.loader.exec_module(cfg)

sensor_validation_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.sensor_validation",
    BASE_PATH / "sensor_validation.py",
)
sensor_validation = importlib.util.module_from_spec(sensor_validation_spec)
sys.modules[sensor_validation_spec.name] = sensor_validation
sensor_validation_spec.loader.exec_module(sensor_validation)

reg_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.profile_registry", BASE_PATH / "profile_registry.py")
reg = importlib.util.module_from_spec(reg_spec)
sys.modules[reg_spec.name] = reg
reg_spec.loader.exec_module(reg)

compat_spec = importlib.util.spec_from_file_location(f"{PACKAGE}.profile.compat", BASE_PATH / "profile" / "compat.py")
compat = importlib.util.module_from_spec(compat_spec)
sys.modules[compat_spec.name] = compat
compat_spec.loader.exec_module(compat)

validation_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.sensor_validation", BASE_PATH / "sensor_validation.py"
)
sensor_validation = importlib.util.module_from_spec(validation_spec)
sys.modules[validation_spec.name] = sensor_validation
validation_spec.loader.exec_module(sensor_validation)

ConfigFlow = cfg.ConfigFlow
OptionsFlow = cfg.OptionsFlow
ProfileRegistry = reg.ProfileRegistry
sync_thresholds = compat.sync_thresholds
SensorSuggestion = cfg.SensorSuggestion
SensorValidationIssue = sensor_validation.SensorValidationIssue
SensorValidationResult = sensor_validation.SensorValidationResult
_normalise_sensor_submission = cfg._normalise_sensor_submission
_sensor_selection_signature = cfg._sensor_selection_signature

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


async def test_normalise_sensor_submission_deduplicates_sequences():
    values = ["sensor.one", "sensor.one", "sensor.two", "", None, "sensor.two"]

    result = _normalise_sensor_submission(values)

    assert result == ["sensor.one", "sensor.two"]


async def test_normalise_sensor_submission_collapses_mappings():
    values = {
        "entity_id": "sensor.primary",
        "option": "sensor.primary",
        "extra": ["sensor.secondary", "sensor.secondary"],
    }

    result = _normalise_sensor_submission(values)

    assert result == ["sensor.primary", "sensor.secondary"]


async def test_sensor_selection_signature_is_stable_for_duplicate_entries():
    signature = _sensor_selection_signature(
        {
            "conductivity": ["sensor.alpha", "sensor.alpha", "sensor.beta"],
            "moisture": {"entity_id": "sensor.shared", "option": "sensor.shared"},
        }
    )

    assert signature == (
        ("conductivity", ("sensor.alpha", "sensor.beta")),
        ("moisture", ("sensor.shared",)),
    )


async def test_threshold_source_falls_back_without_select_selector(hass):
    """Ensure the method selector gracefully degrades when selectors are unsupported."""

    flow = ConfigFlow()
    flow.hass = hass
    flow._config = {}
    flow._profile = {
        CONF_PLANT_ID: "mint",
        CONF_PLANT_NAME: "Mint",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }
    flow._async_available_profile_templates = AsyncMock(return_value={})

    with (
        patch.object(sel, "SelectSelector", side_effect=TypeError("unsupported")),
        patch.object(sel, "SelectSelectorConfig", side_effect=TypeError("unsupported"), create=True),
    ):
        first = await flow.async_step_threshold_source()

        assert first["type"] == "form"
        assert first["step_id"] == "threshold_source"

        follow_up = await flow.async_step_threshold_source({"method": "manual"})

    assert follow_up["type"] == "form"
    assert follow_up["step_id"] == "thresholds"


@pytest.fixture(autouse=True)
def _mock_socket():
    import socket as socket_mod

    original_socket = socket_mod.socket

    class GuardedSocket:
        def __init__(self, sock):
            self._sock = sock
            self._nonblocking = False

        def setblocking(self, flag):  # pragma: no cover - simple wrapper
            result = self._sock.setblocking(flag)
            self._nonblocking = flag is False
            return result

        def connect(self, *conn_args, **conn_kwargs):  # pragma: no cover - ensure non-blocking
            if not self._nonblocking:
                raise ValueError("the socket must be non-blocking")
            return self._sock.connect(*conn_args, **conn_kwargs)

        def __getattr__(self, attr):  # pragma: no cover - proxy remaining attributes
            return getattr(self._sock, attr)

    def guard_socket(*args, **kwargs):
        return GuardedSocket(original_socket(*args, **kwargs))

    with (
        patch("socket.socket", side_effect=guard_socket),
        patch(
            "socket.create_connection",
            side_effect=ValueError("the socket must be non-blocking"),
        ),
    ):
        yield


async def begin_profile_flow(flow):
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    result = await flow.async_step_user({"setup_mode": "profile"})
    assert result["type"] == "form"
    assert result["step_id"] == "profile"
    return result


async def test_config_flow_user(hass):
    """Test user config flow."""
    flow = ConfigFlow()
    flow.hass = hass
    first = await flow.async_step_user()
    assert first["type"] == "form"
    assert first["step_id"] == "user"
    result = await flow.async_step_user({"setup_mode": "profile"})
    assert result["type"] == "form"
    assert result["step_id"] == "profile"

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"plant_type": "herb", "sensor_entities": {}}
        path.write_text(json.dumps(data), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run) as exec_mock,
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ) as gen_mock,
    ):
        result3 = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "threshold_source"
        result4 = await flow.async_step_threshold_source({"method": "manual"})
        assert result4["type"] == "form"
        assert result4["step_id"] == "thresholds"
        hass.states.async_set(
            "sensor.good",
            0,
            {"device_class": "moisture", "unit_of_measurement": "%"},
        )
        result4 = await flow.async_step_thresholds({})
        assert result4["type"] == "form"
        assert result4["step_id"] == "sensors"
        assert "sensor.good" in result4["description_placeholders"]["sensor_hints"]
        result5 = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})
    assert result5["type"] == "create_entry"
    assert result5["data"][CONF_PLANT_NAME] == "Mint"
    assert result5["data"][CONF_PLANT_ID] == "mint"
    options = result5["options"]
    assert options["moisture_sensor"] == "sensor.good"
    assert options["sensors"] == {"moisture": "sensor.good"}
    assert options["thresholds"] == {}
    assert options["resolved_targets"] == {}
    assert options["variables"] == {}
    assert CONF_PROFILES in options
    profiles = options[CONF_PROFILES]
    assert set(profiles) == {"mint"}
    profile_opts = profiles["mint"]
    assert profile_opts["name"] == "Mint"
    assert profile_opts["plant_id"] == "mint"
    assert profile_opts["sensors"]["moisture"] == "sensor.good"
    assert profile_opts["thresholds"] == {}
    general = profile_opts["general"]
    assert general["sensors"]["moisture"] == "sensor.good"
    assert general["plant_type"] == "Herb"
    assert general[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert profile_opts[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert exec_mock.call_count == 3
    gen_mock.assert_called_once()
    general = json.loads(Path(hass.config.path("plants", "mint", "general.json")).read_text())
    assert general["sensor_entities"] == {"moisture_sensors": ["sensor.good"]}
    assert general["plant_type"] == "herb"
    registry = json.loads(Path(hass.config.path("data", "local", "plants", "plant_registry.json")).read_text())
    assert registry["mint"]["display_name"] == "Mint"
    assert registry["mint"]["plant_type"] == "Herb"


@pytest.mark.asyncio
async def test_config_flow_register_plant_failure_does_not_block_profile(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.register_plant",
            side_effect=RuntimeError("registry unavailable"),
        ) as register_mock,
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})

    assert result["type"] == "create_entry"
    assert register_mock.called


@pytest.mark.asyncio
async def test_config_flow_sensor_validation_failure_does_not_abort(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.validate_sensor_links",
            side_effect=RuntimeError("validation unavailable"),
        ) as validate_mock,
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})

    assert result["type"] == "create_entry"
    assert validate_mock.called


@pytest.mark.asyncio
async def test_config_flow_sensor_persistence_failure_does_not_abort(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.save_json",
            side_effect=OSError("disk full"),
        ) as save_mock,
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})

    assert result["type"] == "create_entry"
    options = result["options"]
    assert options["sensors"] == {"moisture": "sensor.good"}
    profiles = options[CONF_PROFILES]
    assert profiles["mint"]["sensors"] == {"moisture": "sensor.good"}
    general = profiles["mint"].get("general", {})
    assert general.get("display_name") == "Mint"
    assert save_mock.called


@pytest.mark.asyncio
async def test_config_flow_profile_completion_error_falls_back(hass, caplog):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    calls: list[tuple[str, str, dict[str, Any], dict[str, Any]]] = []

    def create_entry_side_effect(*, title: str, data: dict[str, Any], options: dict[str, Any]):
        if not calls:
            calls.append(("fail", title, data, options))
            raise RuntimeError("boom")
        calls.append(("success", title, data, options))
        return {"type": "create_entry", "title": title, "data": data, "options": options}

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch.object(
            ConfigFlow,
            "async_create_entry",
            side_effect=create_entry_side_effect,
        ) as create_entry,
        caplog.at_level(logging.ERROR),
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})

    assert result["type"] == "create_entry"
    assert create_entry.call_count == 2
    assert calls[0][0] == "fail"
    assert calls[1][0] == "success"
    assert result["options"]["sensors"] == {"moisture": "sensor.good"}
    profiles = result["options"][CONF_PROFILES]
    assert profiles["mint"]["general"]["display_name"] == "Mint"
    assert profiles["mint"]["thresholds"] == {}
    assert any("storing manual fallback" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_config_flow_sensor_suggestions_failure_is_non_blocking(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.collect_sensor_suggestions",
            side_effect=RuntimeError("catalog unavailable"),
        ) as suggestion_mock,
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        result = await flow.async_step_thresholds({})

    assert suggestion_mock.called
    assert result["type"] == "form"
    assert result["step_id"] == "sensors"
    hints = result["description_placeholders"].get("sensor_hints", "")
    assert "No matching sensors detected." in hints


@pytest.mark.asyncio
async def test_config_flow_sensor_suggestions_with_unexpected_shapes(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    class SuggestionStub:
        def __init__(self, entity_id: str, name: str, score: int = 0, reason: str = "") -> None:
            self.entity_id = entity_id
            self.name = name
            self.score = score
            self.reason = reason

    class WeirdSuggestion:
        def __init__(self) -> None:
            self.id = "sensor.weird"
            self.label = "Weird Sensor"

    suggestions = {role: [] for role in cfg.SENSOR_OPTION_ROLES.values()}
    suggestions["moisture"] = [
        {"name": "Missing Identifier"},
        {"entity_id": ["sensor.dict_primary", "sensor.dict_secondary"], "label": "Dict Sensor"},
        SuggestionStub("sensor.stub", "Stub Sensor", 3, "scored"),
        WeirdSuggestion(),
        ("sensor.tuple", "Tuple Sensor"),
        {"value": "sensor.value", "title": "Value Sensor"},
        ["sensor.sequence", "ignored"],
        object(),
    ]

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.collect_sensor_suggestions",
            return_value=suggestions,
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        result = await flow.async_step_thresholds({})

    assert result["type"] == "form"
    assert result["step_id"] == "sensors"
    hints = result["description_placeholders"].get("sensor_hints", "")
    assert "Dict Sensor (sensor.dict_primary)" in hints
    assert "Stub Sensor (sensor.stub)" in hints
    assert "Weird Sensor (sensor.weird)" in hints
    assert "Missing Identifier" not in hints


@pytest.mark.asyncio
async def test_config_flow_sensor_suggestions_iterable_failure_is_non_blocking(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    class ExplodingIterable:
        def __iter__(self):
            raise RuntimeError("catalog iteration failed")

    suggestions = {role: [] for role in cfg.SENSOR_OPTION_ROLES.values()}
    suggestions["moisture"] = ExplodingIterable()

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.collect_sensor_suggestions",
            return_value=suggestions,
        ) as suggestion_mock,
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        result = await flow.async_step_thresholds({})

    assert suggestion_mock.called
    assert result["type"] == "form"
    assert result["step_id"] == "sensors"
    hints = result["description_placeholders"].get("sensor_hints", "")
    assert "No matching sensors detected." in hints


@pytest.mark.asyncio
async def test_config_flow_profile_sections_failure_does_not_abort(hass):
    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.ensure_sections",
            side_effect=RuntimeError("failed"),
        ),
        patch("custom_components.horticulture_assistant.config_flow._LOGGER") as logger,
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({})

    assert result["type"] == "create_entry"
    assert result["title"] == "Mint"
    options = result["options"]
    profiles = options.get(CONF_PROFILES, {})
    assert "mint" in profiles
    profile_opts = profiles["mint"]
    assert profile_opts["name"] == "Mint"
    assert profile_opts["plant_id"] == "mint"
    assert profile_opts.get("library") == {}
    assert profile_opts.get("local") == {}
    sections = profile_opts.get("sections")
    assert isinstance(sections, Mapping)
    assert sections.get("library") == {}
    assert sections.get("local") == {}
    general = profile_opts.get("general")
    assert isinstance(general, Mapping)
    assert general.get(CONF_PROFILE_SCOPE) == PROFILE_SCOPE_DEFAULT
    assert general.get("display_name") == "Mint"
    logger.warning.assert_called()


async def test_config_flow_skip_initial_profile(hass):
    flow = ConfigFlow()
    flow.hass = hass
    hass.config.location_name = "Greenhouse"
    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    outcome = await flow.async_step_user({"setup_mode": "skip"})
    assert outcome["type"] == "create_entry"
    assert outcome["title"] == "Greenhouse"
    assert outcome["data"] == {}
    assert outcome["options"] == {}


async def test_config_flow_copy_profile_from_existing_entry(hass):
    existing_profile = {
        "name": "Basil Template",
        "plant_id": "basil",
        "thresholds": {
            "temperature_min": 12.0,
            "temperature_max": 28.0,
            "humidity_min": 40.0,
            "humidity_max": 70.0,
        },
        "general": {
            "plant_type": "herb",
            CONF_PROFILE_SCOPE: "species_template",
            "sensors": {"moisture": "sensor.copy_moisture"},
        },
        "sensors": {"moisture": "sensor.copy_moisture"},
        CONF_PROFILE_SCOPE: "species_template",
        "species_display": "Ocimum basilicum",
        "species_pid": "opb:basil",
        "image_url": "https://example.com/basil.jpg",
        "opb_credentials": {"client_id": "abc", "secret": "xyz"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_PROFILES: {"basil": existing_profile}},
    )
    entry.add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass
    flow._async_current_entries = MagicMock(return_value=[entry])

    hass.states.async_set(
        "sensor.copy_moisture",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint_clone"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "post_setup"

    result = await flow.async_step_post_setup({"next_action": "add_profile"})
    assert result["type"] == "form"
    assert result["step_id"] == "profile"

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch.object(hass.config_entries, "async_update_entry") as update_mock,
    ):
        profile_result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint Clone",
                CONF_PLANT_TYPE: "",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        assert profile_result["step_id"] == "threshold_source"

        source_result = await flow.async_step_threshold_source({"method": "copy"})
        assert source_result["type"] == "form"
        assert source_result["step_id"] == "threshold_copy"

        copy_result = await flow.async_step_threshold_copy({"profile_id": "basil"})
        assert copy_result["type"] == "form"
        assert copy_result["step_id"] == "thresholds"
        assert flow._sensor_defaults == {CONF_MOISTURE_SENSOR: "sensor.copy_moisture"}
        assert flow._species_display == "Ocimum basilicum"
        assert flow._species_pid == "opb:basil"

        thresholds_result = await flow.async_step_thresholds({})
        assert thresholds_result["type"] == "form"
        assert thresholds_result["step_id"] == "sensors"

        sensors_result = await flow.async_step_sensors({CONF_MOISTURE_SENSOR: "sensor.copy_moisture"})

    assert sensors_result["type"] == "abort"
    assert sensors_result["reason"] == "profile_added"

    update_mock.assert_called_once()
    stored_options = update_mock.call_args.kwargs["options"]
    stored_profiles = stored_options[CONF_PROFILES]
    assert set(stored_profiles) == {"basil", "mint_clone"}
    new_profile = stored_profiles["mint_clone"]
    assert new_profile["thresholds"]["temperature_min"] == 12.0
    assert new_profile["species_display"] == "Ocimum basilicum"
    assert new_profile["species_pid"] == "opb:basil"
    assert new_profile["sensors"]["moisture"] == "sensor.copy_moisture"
    assert new_profile["opb_credentials"]["client_id"] == "abc"


async def test_config_flow_copy_profile_from_library_template(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    from custom_components.horticulture_assistant.profile_store import ProfileStore

    store = ProfileStore(hass)
    await store.async_init()
    await store.async_save(
        {
            "name": "Library Basil",
            "plant_id": "library_basil",
            "thresholds": {"temperature_min": 14.0},
            "general": {
                "plant_type": "Herb",
                CONF_PROFILE_SCOPE: "species_template",
                "sensors": {"temperature": "sensor.library_temp"},
            },
            "sensors": {"temperature": "sensor.library_temp"},
            "species_display": "Ocimum basilicum",
        },
        name="Library Basil",
    )

    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "library_mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "Herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Library Mint",
                CONF_PLANT_TYPE: "",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )

        templates = await flow._async_available_profile_templates()
        library_id = next(key for key, data in templates.items() if data.get("name") == "Library Basil")
        assert flow._profile_template_sources[library_id] == "library"

        copy_form = await flow.async_step_threshold_source({"method": "copy"})
        assert copy_form["type"] == "form"
        assert copy_form["step_id"] == "threshold_copy"

        copy_result = await flow.async_step_threshold_copy({"profile_id": library_id})
        assert copy_result["type"] == "form"
        assert copy_result["step_id"] == "thresholds"
        assert flow._sensor_defaults == {CONF_TEMPERATURE_SENSOR: "sensor.library_temp"}
        assert flow._species_display == "Ocimum basilicum"

        thresholds_result = await flow.async_step_thresholds({})
        assert thresholds_result["type"] == "form"
        assert thresholds_result["step_id"] == "sensors"

        sensors_result = await flow.async_step_sensors({})

    assert sensors_result["type"] == "create_entry"
    options = sensors_result["options"]
    profiles = options[CONF_PROFILES]
    assert set(profiles) == {"library_mint"}
    stored_profile = profiles["library_mint"]
    assert stored_profile["thresholds"]["temperature_min"] == 14.0
    assert stored_profile["general"][CONF_PROFILE_SCOPE] == "species_template"
    assert stored_profile[CONF_PROFILE_SCOPE] == "species_template"
    assert stored_profile["species_display"] == "Ocimum basilicum"
    assert stored_profile["sensors"]["temperature"] == "sensor.library_temp"


async def test_config_flow_library_template_load_failure_falls_back_to_manual(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "library_failure_mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return plant_id

    store = AsyncMock()
    store.async_list.return_value = ["broken_template"]
    store.async_get.side_effect = RuntimeError("template load failed")
    flow._profile_store = store

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
    ):
        profile_result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Library Failure Mint",
                CONF_PLANT_TYPE: "",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        assert profile_result["step_id"] == "threshold_source"

        source_form = await flow.async_step_threshold_source()
        assert source_form["type"] == "form"
        assert source_form["step_id"] == "threshold_source"
        assert flow._profile_templates == {}
        assert flow._profile_template_sources == {}

        manual_result = await flow.async_step_threshold_source({"method": "manual"})
        assert manual_result["type"] == "form"
        assert manual_result["step_id"] == "thresholds"

        thresholds_result = await flow.async_step_thresholds({})
        assert thresholds_result["type"] == "form"
        assert thresholds_result["step_id"] == "sensors"

        sensors_result = await flow.async_step_sensors({})

    assert sensors_result["type"] == "create_entry"
    profiles = sensors_result["options"][CONF_PROFILES]
    assert set(profiles) == {"library_failure_mint"}

    store.async_list.assert_awaited_once()
    store.async_get.assert_awaited_once_with("broken_template")


async def test_config_flow_library_template_iteration_failure_falls_back_to_manual(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "library_iterator_mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return plant_id

    class ExplodingIterable:
        def __iter__(self):
            raise RuntimeError("iterator failed")

    store = AsyncMock()
    store.async_list.return_value = ExplodingIterable()
    store.async_get.return_value = {}
    flow._profile_store = store

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
    ):
        profile_result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Library Iterator Mint",
                CONF_PLANT_TYPE: "",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        assert profile_result["step_id"] == "threshold_source"

        source_form = await flow.async_step_threshold_source()
        assert source_form["type"] == "form"
        assert source_form["step_id"] == "threshold_source"
        assert flow._profile_templates == {}
        assert flow._profile_template_sources == {}

        manual_result = await flow.async_step_threshold_source({"method": "manual"})
        assert manual_result["type"] == "form"
        assert manual_result["step_id"] == "thresholds"

        thresholds_result = await flow.async_step_thresholds({})
        assert thresholds_result["type"] == "form"
        assert thresholds_result["step_id"] == "sensors"

        sensors_result = await flow.async_step_sensors({})

    assert sensors_result["type"] == "create_entry"
    profiles = sensors_result["options"][CONF_PROFILES]
    assert set(profiles) == {"library_iterator_mint"}

    store.async_list.assert_awaited_once()
    store.async_get.assert_not_awaited()


async def test_config_flow_threshold_copy_sync_failure_falls_back_to_manual(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    from custom_components.horticulture_assistant.profile_store import ProfileStore

    store = ProfileStore(hass)
    await store.async_init()
    await store.async_save(
        {
            "name": "Library Basil",
            "plant_id": "library_basil",
            "thresholds": {"temperature_min": 14.0, "temperature_max": 26.0},
            "general": {
                "plant_type": "Herb",
                CONF_PROFILE_SCOPE: "species_template",
                "sensors": {"temperature": "sensor.library_temp"},
            },
            "sensors": {"temperature": "sensor.library_temp"},
            "species_display": "Ocimum basilicum",
        },
        name="Library Basil",
    )

    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "library_mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "Herb"}), encoding="utf-8")
        return plant_id

    real_sync = sync_thresholds
    call_count = 0

    def guarded_sync(payload, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("sync failure")
        return real_sync(payload, *args, **kwargs)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.sync_thresholds",
            side_effect=guarded_sync,
        ) as sync_mock,
    ):
        profile_result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Library Mint",
                CONF_PLANT_TYPE: "",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        assert profile_result["step_id"] == "threshold_source"

        templates = await flow._async_available_profile_templates()
        library_id = next(key for key, data in templates.items() if data.get("name") == "Library Basil")

        copy_form = await flow.async_step_threshold_source({"method": "copy"})
        assert copy_form["type"] == "form"
        assert copy_form["step_id"] == "threshold_copy"

        copy_result = await flow.async_step_threshold_copy({"profile_id": library_id})
        assert copy_result["type"] == "form"
        assert copy_result["step_id"] == "thresholds"

        snapshot = flow._threshold_snapshot
        assert isinstance(snapshot, Mapping)
        assert snapshot["thresholds"]["temperature_min"] == 14.0
        resolved = snapshot["resolved_targets"]["temperature_min"]
        assert resolved["value"] == 14.0
        assert resolved["annotation"]["method"] == "manual"
        sections = snapshot.get("sections", {})
        assert sections["resolved"]["thresholds"]["temperature_min"] == 14.0

        thresholds_result = await flow.async_step_thresholds({})
        assert thresholds_result["step_id"] == "sensors"

        sensors_result = await flow.async_step_sensors({})

    assert sensors_result["type"] == "create_entry"
    profiles = sensors_result["options"][CONF_PROFILES]
    stored_profile = profiles["library_mint"]
    assert stored_profile["thresholds"]["temperature_min"] == 14.0
    resolved_target = stored_profile["resolved_targets"]["temperature_min"]
    assert resolved_target["annotation"]["method"] == "manual"
    assert sync_mock.call_count >= 1


async def test_config_flow_copy_profile_filtering(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    from custom_components.horticulture_assistant.profile_store import ProfileStore

    store = ProfileStore(hass)
    await store.async_init()
    await store.async_save(
        {
            "name": "Library Basil",
            "plant_id": "library_basil",
            "thresholds": {"temperature_min": 14.0},
            "general": {
                "plant_type": "Herb",
                CONF_PROFILE_SCOPE: "species_template",
                "sensors": {"temperature": "sensor.library_temp"},
            },
            "sensors": {"temperature": "sensor.library_temp"},
            "species_display": "Ocimum basilicum",
        },
        name="Library Basil",
    )

    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    existing_profiles = {
        "installed_mint": {
            "name": "Installed Mint",
            "plant_id": "installed_mint",
            "thresholds": {"temperature_min": 10.0},
            "general": {
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            },
            "sensors": {"temperature": "sensor.entry_temp"},
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
        }
    }
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={CONF_PROFILES: existing_profiles})
    entry.add_to_hass(hass)
    flow._profile_templates = None
    flow._profile_template_sources = {}

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "library_mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "Herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Library Mint",
                CONF_PLANT_TYPE: "",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )

        templates = await flow._async_available_profile_templates()
        library_id = next(key for key, data in templates.items() if data.get("name") == "Library Basil")
        entry_id = next(key for key, data in templates.items() if data.get("name") == "Installed Mint")
        assert flow._profile_template_sources[library_id] == "library"
        assert flow._profile_template_sources[entry_id] == "entry"

        copy_form = await flow.async_step_threshold_source({"method": "copy"})
        assert copy_form["type"] == "form"
        assert copy_form["step_id"] == "threshold_copy"

        def _selector_options(form):
            schema = form["data_schema"]
            for key, value in schema.schema.items():
                if getattr(key, "schema", None) == "profile_id":
                    return value.config.options
            return []

        library_form = await flow.async_step_threshold_copy({"filter": "source:library"})
        assert library_form["errors"] == {}
        assert flow._template_filter == "source:library"
        library_options = _selector_options(library_form)
        assert library_options
        assert all(option["label"].startswith("[Library]") for option in library_options)
        summary = library_form["description_placeholders"].get("filter_summary")
        assert summary
        assert "Library templates" in summary

        entry_form = await flow.async_step_threshold_copy({"filter": "source:entry"})
        assert entry_form["errors"] == {}
        assert flow._template_filter == "source:entry"
        entry_options = _selector_options(entry_form)
        assert entry_options
        assert all(not option["label"].startswith("[Library]") for option in entry_options)
        entry_summary = entry_form["description_placeholders"].get("filter_summary")
        assert entry_summary
        assert "Existing entries" in entry_summary

        scope_form = await flow.async_step_threshold_copy({"filter": "scope:species"})
        assert scope_form["errors"] == {}
        assert flow._template_filter == "scope:species"
        scope_options = _selector_options(scope_form)
        assert scope_options
        assert all(option["label"].startswith("[Library]") for option in scope_options)
        scope_summary = scope_form["description_placeholders"].get("filter_summary")
        assert scope_summary
        assert "Species template" in scope_summary

        combined_filter = "Mint scope:individual source:entry"
        combined_form = await flow.async_step_threshold_copy({"filter": combined_filter})
        assert combined_form["errors"] == {}
        assert flow._template_filter == combined_filter
        combined_options = _selector_options(combined_form)
        assert combined_options == entry_options
        combined_summary = combined_form["description_placeholders"].get("filter_summary")
        assert "Mint" in combined_summary
        assert "Individual plant" in combined_summary

        no_match = await flow.async_step_threshold_copy({"filter": "orchid", "profile_id": ""})
        assert no_match["type"] == "form"
        assert no_match["step_id"] == "threshold_copy"
        assert no_match["errors"] == {"base": "no_template_matches"}
        assert flow._template_filter == "orchid"
        assert "orchid" in no_match["description_placeholders"].get("filter_summary", "").lower()

        reset_result = await flow.async_step_threshold_copy({"filter": "", "profile_id": ""})
        assert reset_result["type"] == "form"
        assert reset_result["step_id"] == "threshold_copy"
        assert reset_result["errors"] == {}
        assert flow._template_filter == ""
        assert reset_result["description_placeholders"].get("filter_summary") == ""

        copy_result = await flow.async_step_threshold_copy({"profile_id": library_id})
        assert copy_result["type"] == "form"
        assert copy_result["step_id"] == "thresholds"
        assert flow._template_filter is None


async def test_config_flow_manual_threshold_values(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        result = await flow.async_step_thresholds(
            {
                "temperature_min": "1",
                "temperature_max": "2",
                "humidity_min": "3",
                "humidity_max": "4",
                "illuminance_min": "5",
                "illuminance_max": "6",
                "conductivity_min": "7",
                "conductivity_max": "8",
            }
        )
    assert result["type"] == "form"
    assert result["step_id"] == "sensors"
    assert flow._thresholds == {
        "temperature_min": 1.0,
        "temperature_max": 2.0,
        "humidity_min": 3.0,
        "humidity_max": 4.0,
        "illuminance_min": 5.0,
        "illuminance_max": 6.0,
        "conductivity_min": 7.0,
        "conductivity_max": 8.0,
    }


async def test_config_flow_threshold_form_uses_number_selectors(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        form = await flow.async_step_threshold_source({"method": "manual"})
        assert form["step_id"] == "thresholds"
        thresholds_form = await flow.async_step_thresholds()

    assert thresholds_form["type"] == "form"
    assert thresholds_form["step_id"] == "thresholds"

    schema = thresholds_form["data_schema"]
    assert isinstance(schema, vol.Schema)

    selector_type = getattr(sel, "NumberSelector", None)

    for option, validator in schema.schema.items():
        field = getattr(option, "schema", option)
        if field not in cfg.MANUAL_THRESHOLD_FIELDS:
            continue
        assert isinstance(validator, vol.Any)
        selectors = []
        for value in validator.validators:
            is_selector = (selector_type is not None and isinstance(value, selector_type)) or (
                selector_type is None and isinstance(value, cfg._CompatNumberSelector)
            )
            if is_selector:
                selectors.append(value)
        assert selectors, f"expected number selector for {field}"
        selector = selectors[0]
        meta = cfg.MANUAL_THRESHOLD_METADATA.get(field, {})
        config_obj = getattr(selector, "config", None)
        if isinstance(config_obj, dict):
            min_val = config_obj.get("min")
            max_val = config_obj.get("max")
            step_val = config_obj.get("step")
            unit_val = config_obj.get("unit_of_measurement")
        else:
            min_val = getattr(config_obj, "min", None)
            max_val = getattr(config_obj, "max", None)
            step_val = getattr(config_obj, "step", None)
            unit_val = getattr(config_obj, "unit_of_measurement", None)
        assert min_val == meta.get("min")
        assert max_val == meta.get("max")
        assert step_val == meta.get("step")
        assert unit_val == meta.get("unit")


async def test_config_flow_existing_entry_menu(hass):
    flow = ConfigFlow()
    flow.hass = hass

    mock_entry = MockConfigEntry(domain=DOMAIN, data={})
    mock_entry.add_to_hass(hass)

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "post_setup"

    abort = await flow.async_step_post_setup({"next_action": "open_options"})
    assert abort == {"type": "abort", "reason": "post_setup_use_options"}


async def test_config_flow_existing_entry_add_profile(hass):
    flow = ConfigFlow()
    flow.hass = hass

    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "post_setup"

    next_step = await flow.async_step_post_setup({"next_action": "add_profile"})
    assert next_step["type"] == "form"
    assert next_step["step_id"] == "profile"

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"plant_type": "herb", "sensor_entities": {}}
        path.write_text(json.dumps(data), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run) as exec_mock,
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ) as gen_mock,
    ):
        result3 = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "threshold_source"
        result4 = await flow.async_step_threshold_source({"method": "manual"})
        assert result4["type"] == "form"
        assert result4["step_id"] == "thresholds"
        hass.states.async_set(
            "sensor.good",
            0,
            {"device_class": "moisture", "unit_of_measurement": "%"},
        )
        result4 = await flow.async_step_thresholds({})
        assert result4["type"] == "form"
        assert result4["step_id"] == "sensors"
        result5 = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})
    await hass.async_block_till_done()
    assert result5["type"] == "abort"
    assert result5["reason"] == "profile_added"
    placeholders = result5.get("description_placeholders")
    assert placeholders and placeholders["profile"] == "Mint"
    options = entry.options
    profiles = options.get(CONF_PROFILES, {})
    assert "mint" in profiles
    profile_opts = profiles["mint"]
    assert profile_opts["name"] == "Mint"
    assert profile_opts["plant_id"] == "mint"
    assert profile_opts["sensors"]["moisture"] == "sensor.good"
    assert profile_opts[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    gen_mock.assert_called_once()
    assert exec_mock.call_count == 3


@pytest.mark.asyncio
async def test_config_flow_threshold_source_defaults_when_missing(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        result = await flow.async_step_threshold_source({})

    assert result["type"] == "form"
    assert result["step_id"] == "thresholds"


@pytest.mark.asyncio
async def test_config_flow_threshold_source_skip(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        result = await flow.async_step_threshold_source({"method": "skip"})

    assert result["type"] == "form"
    assert result["step_id"] == "sensors"
    assert flow._thresholds == {}
    assert flow._threshold_snapshot is None


@pytest.mark.asyncio
async def test_config_flow_threshold_source_accepts_selector_payload(hass):
    flow = ConfigFlow()
    flow.hass = hass
    flow._profile = {
        CONF_PLANT_NAME: "Mint",
        CONF_PLANT_ID: "mint",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    skip_payload = {"method": {"value": "skip", "label": "Skip for now"}}
    result_skip = await flow.async_step_threshold_source(skip_payload)
    assert result_skip["type"] == "form"
    assert result_skip["step_id"] == "sensors"

    flow2 = ConfigFlow()
    flow2.hass = hass
    flow2._profile = {
        CONF_PLANT_NAME: "Basil",
        CONF_PLANT_ID: "basil",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    manual_payload = {"method": [{"value": "manual", "label": "Manual entry"}]}
    result_manual = await flow2.async_step_threshold_source(manual_payload)
    assert result_manual["type"] == "form"
    assert result_manual["step_id"] == "thresholds"


async def test_config_flow_threshold_source_accepts_option_objects(hass):
    class DummyOption:
        def __init__(self, value, label):
            self.value = value
            self.label = label

    flow = ConfigFlow()
    flow.hass = hass
    flow._profile = {
        CONF_PLANT_NAME: "Rosemary",
        CONF_PLANT_ID: "rosemary",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    skip_option = DummyOption("skip", "Skip for now")
    result_skip = await flow.async_step_threshold_source({"method": skip_option})
    assert result_skip["type"] == "form"
    assert result_skip["step_id"] == "sensors"

    flow2 = ConfigFlow()
    flow2.hass = hass
    flow2._profile = {
        CONF_PLANT_NAME: "Lavender",
        CONF_PLANT_ID: "lavender",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    manual_option = DummyOption("manual", "Manual entry")
    result_manual = await flow2.async_step_threshold_source({"method": manual_option})
    assert result_manual["type"] == "form"
    assert result_manual["step_id"] == "thresholds"


async def test_config_flow_threshold_source_walks_nested_option_values(hass):
    class NestedValue:
        def __init__(self, value):
            self.value = value

    class NestedOption:
        def __init__(self, value, label):
            self.value = NestedValue(value)
            self.label = label

    flow = ConfigFlow()
    flow.hass = hass
    flow._profile = {
        CONF_PLANT_NAME: "Basil",
        CONF_PLANT_ID: "basil",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    nested_skip = NestedOption("skip", "Skip for now")
    result_skip = await flow.async_step_threshold_source({"method": nested_skip})

    assert result_skip["type"] == "form"
    assert result_skip["step_id"] == "sensors"

    flow2 = ConfigFlow()
    flow2.hass = hass
    flow2._profile = {
        CONF_PLANT_NAME: "Mint",
        CONF_PLANT_ID: "mint",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    nested_manual = NestedOption("manual", "Manual entry")
    result_manual = await flow2.async_step_threshold_source({"method": nested_manual})

    assert result_manual["type"] == "form"
    assert result_manual["step_id"] == "thresholds"


async def test_config_flow_threshold_source_accepts_label_strings(hass):
    flow = ConfigFlow()
    flow.hass = hass
    flow._profile = {
        CONF_PLANT_NAME: "Basil",
        CONF_PLANT_ID: "basil",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    skip_result = await flow.async_step_threshold_source({"method": "Skip for now"})
    assert skip_result["type"] == "form"
    assert skip_result["step_id"] == "sensors"

    flow2 = ConfigFlow()
    flow2.hass = hass
    flow2._profile = {
        CONF_PLANT_NAME: "Mint",
        CONF_PLANT_ID: "mint",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }

    manual_result = await flow2.async_step_threshold_source({"method": "Manual entry"})
    assert manual_result["type"] == "form"
    assert manual_result["step_id"] == "thresholds"


async def test_config_flow_threshold_source_label_paths_trigger_actions(hass):
    flow = ConfigFlow()
    flow.hass = hass
    flow._profile = {
        CONF_PLANT_NAME: "Parsley",
        CONF_PLANT_ID: "parsley",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }
    flow._async_available_profile_templates = AsyncMock(return_value={"template": {}})
    flow.async_step_threshold_copy = AsyncMock(return_value={"type": "form", "step_id": "copy"})

    copy_result = await flow.async_step_threshold_source({"method": "Copy an existing profile"})

    assert copy_result["type"] == "form"
    assert copy_result["step_id"] == "copy"
    flow.async_step_threshold_copy.assert_awaited_once()

    flow2 = ConfigFlow()
    flow2.hass = hass
    flow2._profile = {
        CONF_PLANT_NAME: "Rosemary",
        CONF_PLANT_ID: "rosemary",
        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
    }
    flow2._async_available_profile_templates = AsyncMock(return_value={})
    flow2.async_step_opb_credentials = AsyncMock(return_value={"type": "form", "step_id": "opb"})

    opb_result = await flow2.async_step_threshold_source({"method": "From OpenPlantbook"})

    assert opb_result["type"] == "form"
    assert opb_result["step_id"] == "opb"
    flow2.async_step_opb_credentials.assert_awaited_once()


async def test_coerce_threshold_source_method_handles_label_synonyms():
    assert cfg._coerce_threshold_source_method(" Skip this step ") == "skip"
    assert cfg._coerce_threshold_source_method("Use OpenPlantbook") == "openplantbook"
    assert cfg._coerce_threshold_source_method("ENTER MANUALLY") == "manual"


async def test_build_threshold_selectors_handles_missing_number_selector(monkeypatch):
    import custom_components.horticulture_assistant.config_flow as config_flow

    monkeypatch.setattr(config_flow.sel, "NumberSelector", None, raising=False)
    monkeypatch.setattr(config_flow.sel, "NumberSelectorConfig", None, raising=False)

    selectors = config_flow._build_threshold_selectors()

    assert selectors == {}


async def test_build_threshold_selectors_falls_back_to_text(monkeypatch):
    import custom_components.horticulture_assistant.config_flow as config_flow

    def dummy_selector(_value):  # pragma: no cover - stub behaviour
        raise TypeError

    monkeypatch.setattr(config_flow.sel, "NumberSelector", dummy_selector, raising=False)
    monkeypatch.setattr(config_flow.sel, "NumberSelectorConfig", None, raising=False)

    selectors = config_flow._build_threshold_selectors()

    assert selectors == {}


async def test_build_select_selector_downgrades_option_shape(monkeypatch):
    import custom_components.horticulture_assistant.config_flow as config_flow

    class DummyConfig:
        def __init__(self, **kwargs):
            self.options = kwargs.get("options", [])
            self.kwargs = kwargs

    class DummySelector:
        def __init__(self, config):
            options = config.options if isinstance(config, DummyConfig) else config.get("options")
            if options and isinstance(options[0], dict):
                raise TypeError("dict options unsupported")
            self.config = config

    monkeypatch.setattr(config_flow.sel, "SelectSelector", DummySelector, raising=False)
    monkeypatch.setattr(config_flow.sel, "SelectSelectorConfig", DummyConfig, raising=False)

    selector = config_flow._build_select_selector(
        [
            {"value": "openplantbook", "label": "From OpenPlantbook"},
            {"value": "manual", "label": "Manual entry"},
        ]
    )

    assert selector is not None
    config = selector.config
    options = getattr(config, "options", config.get("options"))
    assert options == ["openplantbook", "manual"]


@pytest.mark.asyncio
async def test_config_flow_sensors_accept_selector_payload(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    flow = ConfigFlow()
    flow.hass = hass

    await begin_profile_flow(flow)

    hass.states.async_set(
        "sensor.soil_probe",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )
    hass.states.async_set(
        "sensor.greenhouse_temperature",
        22,
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        return "selector_plant"

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Selector Plant", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})
        await flow.async_step_threshold_source({"method": "manual"})
        thresholds_form = await flow.async_step_thresholds({})
        assert thresholds_form["type"] == "form"
        assert thresholds_form["step_id"] == "sensors"

        sensor_payload = {
            CONF_MOISTURE_SENSOR: {"entity_id": "sensor.soil_probe"},
            CONF_TEMPERATURE_SENSOR: ["sensor.greenhouse_temperature", "sensor.backup_temp"],
        }

        result = await flow.async_step_sensors(sensor_payload)

    assert result["type"] == "create_entry"
    options = result["options"]
    assert options[CONF_MOISTURE_SENSOR] == "sensor.soil_probe"
    assert options[CONF_TEMPERATURE_SENSOR] == "sensor.greenhouse_temperature"
    assert options["sensors"] == {
        "moisture": "sensor.soil_probe",
        "temperature": "sensor.greenhouse_temperature",
    }
    profile_entry = options[CONF_PROFILES]["selector_plant"]
    general = profile_entry["general"]
    assert general["sensors"]["moisture"] == "sensor.soil_probe"
    assert general["sensors"]["temperature"] == "sensor.greenhouse_temperature"


@pytest.mark.asyncio
async def test_config_flow_threshold_range_validation(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        result = await flow.async_step_thresholds(
            {
                "temperature_min": "90",
                "temperature_max": "10",
            }
        )

    assert result["type"] == "form"
    assert result["errors"]["temperature_min"] == "threshold_field_error"
    assert result["errors"]["temperature_max"] == "threshold_field_error"
    assert result["errors"]["base"] == "threshold_out_of_bounds"
    detail = result.get("description_placeholders", {}).get("issue_detail", "")
    assert "temperature_min=90" in detail
    assert "temperature_max" in detail


async def test_config_flow_profile_generation_failure_falls_back(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return ""

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "threshold_source"
    assert flow._profile[CONF_PLANT_ID] == "mint"


async def test_config_flow_profile_generation_exception_falls_back(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=RuntimeError("boom"),
        ),
    ):
        result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )

    assert result["type"] == "form"
    assert result["step_id"] == "threshold_source"
    assert flow._profile[CONF_PLANT_ID] == "mint"


async def test_config_flow_profile_error_when_no_fallback_identifier(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return ""

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch("custom_components.horticulture_assistant.config_flow.slugify", return_value=""),
    ):
        result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "profile_error"}


async def test_config_flow_profile_fallback_creates_general_file_without_sensors(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    plant_dir = Path(hass.config.path("plants", "mint"))
    if plant_dir.exists():
        shutil.rmtree(plant_dir)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="",
        ),
    ):
        result = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )
        assert result["type"] == "form"
        assert result["step_id"] == "threshold_source"

        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        final = await flow.async_step_sensors({})

    assert final["type"] == "create_entry"
    general_path = Path(hass.config.path("plants", "mint", "general.json"))
    assert general_path.exists()
    general = json.loads(general_path.read_text())
    assert general["display_name"] == "Mint"
    assert general["plant_type"] == "herb"
    assert general[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert "sensor_entities" not in general or general["sensor_entities"] == {}


async def test_config_flow_profile_fallback_avoids_duplicate_identifier(hass, tmp_path, monkeypatch):
    monkeypatch.setattr(hass.config, "path", lambda *parts: str(tmp_path.joinpath(*parts)))

    existing_profiles = {
        "mint": {
            "name": "Existing Mint",
            "plant_id": "mint",
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            "general": {"display_name": "Existing Mint", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "mint"},
        options={CONF_PROFILES: existing_profiles},
    )
    entry.add_to_hass(hass)

    flow = ConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "post_setup"

    next_step = await flow.async_step_post_setup({"next_action": "add_profile"})
    assert next_step["type"] == "form"
    assert next_step["step_id"] == "profile"

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=RuntimeError("boom"),
        ),
    ):
        result_profile = await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )

    assert result_profile["type"] == "form"
    assert result_profile["step_id"] == "threshold_source"
    assert flow._profile[CONF_PLANT_ID] == "mint_2"

    result_threshold_source = await flow.async_step_threshold_source({"method": "manual"})
    assert result_threshold_source["type"] == "form"
    assert result_threshold_source["step_id"] == "thresholds"

    result_thresholds = await flow.async_step_thresholds({})
    assert result_thresholds["type"] == "form"
    assert result_thresholds["step_id"] == "sensors"

    result_sensors = await flow.async_step_sensors({})
    await hass.async_block_till_done()
    assert result_sensors["type"] == "abort"
    assert result_sensors["reason"] == "profile_added"

    profiles = entry.options.get(CONF_PROFILES, {})
    assert set(profiles) == {"mint", "mint_2"}
    assert profiles["mint"]["name"] == "Existing Mint"
    assert profiles["mint_2"]["name"] == "Mint"
    assert profiles["mint_2"]["plant_id"] == "mint_2"

    general_path = Path(tmp_path / "plants" / "mint_2" / "general.json")
    assert general_path.exists()
    general_data = json.loads(general_path.read_text())
    assert general_data["plant_id"] == "mint_2"
    assert general_data["display_name"] == "Mint"


async def test_config_flow_profile_requires_name(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)
    result = await flow.async_step_profile(
        {
            CONF_PLANT_NAME: "",
            CONF_PLANT_TYPE: "Herb",
        }
    )
    assert result["type"] == "form"
    assert result["errors"] == {CONF_PLANT_NAME: "required"}


async def test_config_flow_sensor_not_found(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.bad"})
    assert result["type"] == "form"
    assert result["errors"] == {"moisture_sensor": "not_found"}


async def test_config_flow_sensor_validation_mapping_payload_handled(hass, caplog):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        general = Path(hass.config.path("plants", plant_id, "general.json"))
        general.parent.mkdir(parents=True, exist_ok=True)
        general.write_text("{}", encoding="utf-8")
        return plant_id

    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.validate_sensor_links",
            return_value={
                "errors": [{"role": "moisture", "issue": "custom_issue"}],
                "warnings": [{"role": "moisture", "issue": "warn"}],
            },
        ),
        patch.object(flow, "_notify_sensor_warnings") as notify_mock,
        patch.object(flow, "_clear_sensor_warning") as clear_mock,
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        caplog.set_level(logging.DEBUG)
        result = await flow.async_step_sensors({CONF_MOISTURE_SENSOR: "sensor.good"})

    assert result["type"] == "form"
    assert result["step_id"] == "sensors"
    assert result["errors"] == {CONF_MOISTURE_SENSOR: "custom_issue"}
    notify_mock.assert_not_called()
    clear_mock.assert_called()
    assert "Dropping sensor warning payload" in caplog.text


async def test_config_flow_sensor_validation_unexpected_payload_does_not_abort(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        general = Path(hass.config.path("plants", plant_id, "general.json"))
        general.parent.mkdir(parents=True, exist_ok=True)
        general.write_text("{}", encoding="utf-8")
        return plant_id

    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.validate_sensor_links",
            return_value=object(),
        ),
        patch.object(flow, "_clear_sensor_warning") as clear_mock,
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({})
        result = await flow.async_step_sensors({CONF_MOISTURE_SENSOR: "sensor.good"})

    assert result["type"] == "create_entry"
    options = result["options"]
    assert options["sensors"]["moisture"] == "sensor.good"
    clear_mock.assert_called()


async def test_config_flow_without_sensors(hass):
    """Profiles can be created without attaching sensors."""
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        await flow.async_step_profile({CONF_PLANT_NAME: "Rose"})
        result_th = await flow.async_step_threshold_source({"method": "skip"})
        assert result_th["type"] == "form" and result_th["step_id"] == "sensors"
        result = await flow.async_step_sensors({})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_PLANT_NAME] == "Rose"
    assert result["data"][CONF_PLANT_ID] == "rose"
    options = result["options"]
    assert options["sensors"] == {}
    assert options["thresholds"] == {}
    assert options["resolved_targets"] == {}
    assert options["variables"] == {}
    profiles = options[CONF_PROFILES]
    assert set(profiles) == {"rose"}
    profile_opts = profiles["rose"]
    assert profile_opts["sensors"] == {}
    assert profile_opts["thresholds"] == {}
    assert profile_opts["general"][CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    general = json.loads(Path(hass.config.path("plants", "rose", "general.json")).read_text())
    sensors = general.get("sensor_entities", {})
    assert all(not values for values in sensors.values())
    registry = json.loads(Path(hass.config.path("data", "local", "plants", "plant_registry.json")).read_text())
    assert registry["rose"]["display_name"] == "Rose"
    assert "plant_type" not in registry["rose"]
    assert general["plant_type"] == "TBD"


async def test_config_flow_threshold_sync_failure_falls_back(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="mint",
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.sync_thresholds",
            side_effect=RuntimeError("sync failed"),
        ),
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        await flow.async_step_thresholds({"temperature_min": "10", "temperature_max": "20"})
        result = await flow.async_step_sensors({})

    assert result["type"] == "create_entry"
    options = result["options"]
    assert options["thresholds"] == {
        "temperature_min": pytest.approx(10.0),
        "temperature_max": pytest.approx(20.0),
    }
    resolved = options["resolved_targets"]
    assert set(resolved) == {"temperature_min", "temperature_max"}
    for key, expected in options["thresholds"].items():
        annotation = resolved[key]["annotation"]
        assert resolved[key]["value"] == pytest.approx(expected)
        assert annotation["source_type"] == "manual"
        assert annotation["method"] == "manual"
    variables = options["variables"]
    for key, payload in variables.items():
        assert payload["value"] == pytest.approx(options["thresholds"][key])
        assert payload["source"] == "manual"
        assert payload["annotation"]["source_type"] == "manual"
    profile_opts = options[CONF_PROFILES]["mint"]
    resolved_section = profile_opts["sections"]["resolved"]
    assert resolved_section["thresholds"] == options["thresholds"]
    assert resolved_section["resolved_targets"] == resolved
    assert resolved_section["variables"] == variables


async def test_config_flow_threshold_validation_failure_does_not_abort(hass, caplog):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args):
        return func(*args)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"plant_type": "herb"}), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.evaluate_threshold_bounds",
            side_effect=RuntimeError("validation failed"),
        ) as evaluate_mock,
    ):
        await flow.async_step_profile(
            {
                CONF_PLANT_NAME: "Mint",
                CONF_PLANT_TYPE: "Herb",
            }
        )
        await flow.async_step_threshold_source({"method": "manual"})
        caplog.set_level(logging.ERROR)
        thresholds_result = await flow.async_step_thresholds({"temperature_min": "10", "temperature_max": "20"})

    assert thresholds_result["type"] == "form"
    assert thresholds_result["step_id"] == "sensors"
    assert "Unable to validate manual thresholds" in caplog.text
    evaluate_mock.assert_called_once()
    assert flow._thresholds == {
        "temperature_min": pytest.approx(10.0),
        "temperature_max": pytest.approx(20.0),
    }

    result = await flow.async_step_sensors({})
    assert result["type"] == "create_entry"
    options = result["options"]
    assert options["thresholds"] == {
        "temperature_min": pytest.approx(10.0),
        "temperature_max": pytest.approx(20.0),
    }


async def test_options_flow(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    hass.states.async_set(
        "sensor.greenhouse_temp",
        22,
        {"device_class": "temperature", "unit_of_measurement": "°C"},
    )
    await flow.async_step_init()
    result = await flow.async_step_basic()
    assert result["type"] == "form"
    assert "sensor.greenhouse_temp" in result["description_placeholders"]["sensor_hints"]
    result2 = await flow.async_step_basic({})
    assert result2["type"] == "create_entry"


async def test_options_flow_menu_hides_profile_actions_without_profiles(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_init()

    assert result["type"] == "menu"
    assert result["menu_options"] == ["basic", "cloud_sync", "add_profile", "configure_ai"]


async def test_options_flow_menu_includes_profile_actions_when_available(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_PROFILES: {"mint": {"name": "Mint", "plant_id": "mint"}}},
        title="title",
    )
    flow = OptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_init()

    assert result["type"] == "menu"
    assert result["menu_options"] == [
        "basic",
        "cloud_sync",
        "add_profile",
        "manage_profiles",
        "configure_ai",
        "profile_targets",
        "nutrient_schedule",
    ]


async def test_options_flow_sensor_validation_failure_does_not_abort(hass, hass_admin_user):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_PLANT_ID: "mint"},
        options={
            CONF_PROFILES: {
                "mint": {
                    "name": "Mint",
                    "plant_id": "mint",
                    "general": {"display_name": "Mint"},
                }
            }
        },
        title="Mint",
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    hass.states.async_set(
        "sensor.good",
        0,
        {"device_class": "moisture", "unit_of_measurement": "%"},
    )
    await flow.async_step_init()
    await flow.async_step_basic()

    with patch(
        "custom_components.horticulture_assistant.config_flow.validate_sensor_links",
        side_effect=RuntimeError("validation offline"),
    ) as validate_mock:
        result = await flow.async_step_basic({CONF_MOISTURE_SENSOR: "sensor.good"})

    assert result["type"] == "create_entry"
    assert validate_mock.called
    assert result["data"][CONF_MOISTURE_SENSOR] == "sensor.good"
    assert result["data"]["sensors"]["moisture"] == "sensor.good"


async def test_options_flow_cloud_sync(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    form = await flow.async_step_cloud_sync()
    assert form["type"] == "form"
    result = await flow.async_step_cloud_sync(
        {
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "token",
            CONF_CLOUD_SYNC_INTERVAL: 120,
        }
    )
    assert result["type"] == "create_entry"
    data = result["data"]
    assert data[CONF_CLOUD_SYNC_ENABLED] is True
    assert data[CONF_CLOUD_BASE_URL] == "https://cloud.example"
    assert data[CONF_CLOUD_TENANT_ID] == "tenant-1"
    assert data[CONF_CLOUD_DEVICE_TOKEN] == "token"
    assert data[CONF_CLOUD_SYNC_INTERVAL] == 120


async def test_options_flow_cloud_sync_disable(hass, hass_admin_user):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        title="title",
        options={
            CONF_CLOUD_SYNC_ENABLED: True,
            CONF_CLOUD_BASE_URL: "https://cloud.example",
            CONF_CLOUD_TENANT_ID: "tenant-1",
            CONF_CLOUD_DEVICE_TOKEN: "token",
            CONF_CLOUD_SYNC_INTERVAL: 120,
        },
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    await flow.async_step_cloud_sync()
    result = await flow.async_step_cloud_sync({CONF_CLOUD_SYNC_ENABLED: False})
    data = result["data"]
    assert data[CONF_CLOUD_SYNC_ENABLED] is False
    assert CONF_CLOUD_DEVICE_TOKEN not in data


async def test_options_flow_preserves_thresholds(hass, hass_admin_user):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        title="title",
        options={"thresholds": {"temperature_min": 2.0}},
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    await flow.async_step_basic()
    result = await flow.async_step_basic({})
    assert result["data"]["thresholds"]["temperature_min"] == 2.0


async def test_options_flow_persists_sensors(hass, hass_admin_user):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_PLANT_ID: "pid", CONF_PLANT_NAME: "Plant"},
        title="title",
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    profile_dir = Path(hass.config.path("plants", "pid"))
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "general.json").write_text("{}")
    hass.states.async_set("sensor.good", 0, {"device_class": "moisture"})

    async def _run(func, *args):
        return func(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        await flow.async_step_init()
        await flow.async_step_basic()
        result = await flow.async_step_basic({"moisture_sensor": "sensor.good"})

    assert result["type"] == "create_entry"
    assert result["data"]["sensors"]["moisture"] == "sensor.good"
    assert result["data"]["moisture_sensor"] == "sensor.good"
    general = json.loads((profile_dir / "general.json").read_text())
    assert general["sensor_entities"]["moisture_sensors"] == ["sensor.good"]


async def test_options_flow_scales_stale_threshold(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_PLANT_ID: "pid", CONF_PLANT_NAME: "Plant"},
        title="title",
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    profile_dir = Path(hass.config.path("plants", "pid"))
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "general.json").write_text("{}")
    hass.states.async_set("sensor.moisture", 0, {"device_class": "moisture", "unit_of_measurement": "%"})

    thresholds: list = []

    def _capture_validate(_hass, sensors, *, stale_after=None):
        thresholds.append(stale_after)
        return sensor_validation.SensorValidationResult(errors=[], warnings=[])

    monkeypatch.setattr(cfg, "validate_sensor_links", _capture_validate)

    async def _run(func, *args):
        return func(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        await flow.async_step_init()
        result = await flow.async_step_basic({"moisture_sensor": "sensor.moisture", "update_interval": 180})

    assert result["type"] == "create_entry"
    assert thresholds
    assert thresholds[-1] == sensor_validation.recommended_stale_after(180)


async def test_options_flow_ec_co2_sensors(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_PLANT_ID: "pid", CONF_PLANT_NAME: "Plant"},
        title="title",
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    profile_dir = Path(hass.config.path("plants", "pid"))
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "general.json").write_text("{}")
    hass.states.async_set("sensor.ec", 0)
    hass.states.async_set("sensor.co2", 400, {"device_class": "carbon_dioxide"})

    async def _run(func, *args):
        return func(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        await flow.async_step_init()
        await flow.async_step_basic()
        result = await flow.async_step_basic({"ec_sensor": "sensor.ec", "co2_sensor": "sensor.co2"})

    assert result["type"] == "create_entry"
    assert result["data"]["ec_sensor"] == "sensor.ec"
    assert result["data"]["co2_sensor"] == "sensor.co2"
    assert result["data"]["sensors"]["conductivity"] == "sensor.ec"
    assert result["data"]["sensors"]["co2"] == "sensor.co2"
    general = json.loads((profile_dir / "general.json").read_text())
    container = general["sensor_entities"]
    assert container["ec_sensors"] == ["sensor.ec"]
    assert container["co2_sensors"] == ["sensor.co2"]


async def test_options_flow_removes_sensor(hass, hass_admin_user):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_PLANT_ID: "pid", CONF_PLANT_NAME: "Plant"},
        title="title",
        options={"moisture_sensor": "sensor.old"},
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    profile_dir = Path(hass.config.path("plants", "pid"))
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "general.json").write_text(json.dumps({"sensor_entities": {"moisture_sensors": ["sensor.old"]}}))

    async def _run(func, *args):
        return func(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        await flow.async_step_init()
        await flow.async_step_basic()
        result = await flow.async_step_basic({})

    assert result["type"] == "create_entry"
    assert result["data"]["sensors"] == {}
    assert "moisture_sensor" not in result["data"]
    general = json.loads((profile_dir / "general.json").read_text())
    sensors = general.get("sensor_entities", {})
    assert "moisture_sensors" not in sensors


async def test_options_flow_invalid_entity(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    result = await flow.async_step_basic()
    assert result["type"] == "form"
    result2 = await flow.async_step_basic({"moisture_sensor": "sensor.bad"})
    assert result2["type"] == "form"
    assert result2["errors"] == {"moisture_sensor": "not_found"}


async def test_options_flow_rejects_non_sensor_entities(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    hass.states.async_set("light.kitchen", "on")

    await flow.async_step_init()
    result = await flow.async_step_basic()
    assert result["type"] == "form"

    result2 = await flow.async_step_basic({"moisture_sensor": "light.kitchen"})

    assert result2["type"] == "form"
    assert result2["errors"] == {"moisture_sensor": "invalid_sensor_domain"}


async def test_options_flow_rejects_shared_sensor_assignments(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    hass.states.async_set(
        "sensor.shared",
        "50",
        {"device_class": "humidity", "unit_of_measurement": "%"},
    )

    await flow.async_step_init()
    result = await flow.async_step_basic()
    assert result["type"] == "form"

    result2 = await flow.async_step_basic(
        {
            CONF_MOISTURE_SENSOR: "sensor.shared",
            CONF_TEMPERATURE_SENSOR: "sensor.shared",
        }
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {
        CONF_MOISTURE_SENSOR: "shared_entity",
        CONF_TEMPERATURE_SENSOR: "shared_entity",
    }


async def test_options_flow_invalid_interval(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    result = await flow.async_step_basic()
    assert result["type"] == "form"
    result2 = await flow.async_step_basic({"update_interval": 0})
    assert result2["type"] == "form"
    assert result2["errors"] == {"update_interval": "invalid_interval"}


async def test_options_force_refresh(hass, hass_admin_user):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_PLANT_ID: "pid", CONF_PLANT_NAME: "Plant"},
        title="title",
    )
    flow = OptionsFlow(entry)
    flow.hass = hass
    profile_dir = Path(hass.config.path("plants", "pid"))
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "general.json").write_text("{}")

    async def _run(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.config_flow.profile_generator.generate_profile",
            return_value="pid",
        ) as gen_mock,
    ):
        await flow.async_step_init()
        await flow.async_step_basic()
        result = await flow.async_step_basic({"species_display": "Tomato", "force_refresh": True})
    assert result["type"] == "create_entry"
    assert result["data"]["species_display"] == "Tomato"
    gen_mock.assert_called_once()
    args = gen_mock.call_args[0]
    assert args[0]["plant_id"] == "pid"
    assert args[0]["plant_type"] == "Tomato"
    assert args[2] is True


async def test_options_flow_openplantbook_fields(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    await flow.async_step_basic()
    result = await flow.async_step_basic(
        {
            "opb_auto_download_images": False,
            "opb_download_dir": "/tmp/opb",
            "opb_location_share": "country",
            "opb_enable_upload": True,
        }
    )
    assert result["type"] == "create_entry"
    data = result["data"]
    assert data["opb_auto_download_images"] is False
    assert data["opb_download_dir"] == "/tmp/opb"
    assert data["opb_location_share"] == "country"
    assert data["opb_enable_upload"] is True


async def test_config_flow_openplantbook_prefill(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args, **kwargs):
        return func(*args, **kwargs)

    def fake_generate(metadata, hass):
        plant_id = "mint"
        path = Path(hass.config.path("plants", plant_id, "general.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"plant_type": "herb", "sensor_entities": {}}
        path.write_text(json.dumps(data), encoding="utf-8")
        return plant_id

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            side_effect=fake_generate,
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint", CONF_PLANT_TYPE: "Herb"})
        with patch(
            "custom_components.horticulture_assistant.config_flow.OpenPlantbookClient",
        ) as mock_client:
            instance = mock_client.return_value
            instance.search = AsyncMock(return_value=[{"pid": "pid123", "display": "Mint"}])
            instance.get_details = AsyncMock(
                return_value={
                    "min_temp": 1,
                    "max_temp": 2,
                    "min_hum": 3,
                    "max_hum": 4,
                    "image_url": "http://example.com/img.jpg",
                }
            )
            instance.download_image = AsyncMock(return_value="/local/mint.jpg")
            await flow.async_step_threshold_source({"method": "openplantbook"})
            await flow.async_step_opb_credentials({"client_id": "id", "secret": "sec"})
            await flow.async_step_opb_species_search({"query": "mint"})
            await flow.async_step_opb_species_select({"pid": "pid123"})
        await flow.async_step_thresholds(
            {"temperature_min": 1, "temperature_max": 2, "humidity_min": 3, "humidity_max": 4}
        )
        hass.states.async_set("sensor.good", 0)
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})
    assert result["type"] == "create_entry"
    assert result["options"]["thresholds"] == {
        "temperature_min": 1,
        "temperature_max": 2,
        "humidity_min": 3,
        "humidity_max": 4,
    }
    resolved = result["options"]["resolved_targets"]
    assert resolved["temperature_min"]["value"] == 1
    assert resolved["temperature_min"]["annotation"]["source_type"] == "manual"
    assert result["options"]["variables"]["temperature_min"]["value"] == 1
    assert result["options"]["image_url"] == "/local/mint.jpg"
    assert result["options"]["species_pid"] == "pid123"
    assert result["options"]["opb_credentials"] == {"client_id": "id", "secret": "sec"}
    profile_opts = result["options"][CONF_PROFILES]["mint"]
    assert profile_opts["thresholds"]["temperature_min"] == 1
    assert profile_opts["species_pid"] == "pid123"
    assert profile_opts["image_url"] == "/local/mint.jpg"


async def test_config_flow_openplantbook_no_auto_download(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args, **kwargs):
        return func(*args, **kwargs)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key"},
        options={"opb_auto_download_images": False, "opb_download_dir": "/tmp/opb"},
    )
    flow._async_current_entries = MagicMock(return_value=[entry])

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="pid",
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.OpenPlantbookClient",
        ) as mock_client,
    ):
        instance = mock_client.return_value
        instance.search = AsyncMock(return_value=[{"pid": "pid123", "display": "Mint"}])
        instance.get_details = AsyncMock(return_value={"image_url": "http://example.com/img.jpg"})
        instance.download_image = AsyncMock(return_value="/local/mint.jpg")
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "openplantbook"})
        await flow.async_step_opb_credentials({"client_id": "id", "secret": "sec"})
        await flow.async_step_opb_species_search({"query": "mint"})
        await flow.async_step_opb_species_select({"pid": "pid123"})
        await flow.async_step_thresholds({})
        hass.states.async_set("sensor.good", 0)
        result = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})
        assert instance.download_image.await_count == 0
    assert result["type"] == "create_entry"
    assert result["options"]["image_url"] == "http://example.com/img.jpg"


async def test_config_flow_opb_missing_sdk(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="pid",
        ),
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "openplantbook"})
        with patch(
            "custom_components.horticulture_assistant.config_flow.OpenPlantbookClient",
            side_effect=RuntimeError,
        ):
            result = await flow.async_step_opb_credentials({"client_id": "id", "secret": "sec"})
    assert result["type"] == "form"
    assert result["errors"] == {"base": "opb_missing"}


async def test_config_flow_opb_search_failure_falls_back(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await begin_profile_flow(flow)

    async def _run(func, *args, **kwargs):
        return func(*args, **kwargs)

    with (
        patch.object(hass, "async_add_executor_job", side_effect=_run),
        patch(
            "custom_components.horticulture_assistant.utils.profile_generator.generate_profile",
            return_value="pid",
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.OpenPlantbookClient",
        ) as mock_client,
    ):
        await flow.async_step_profile({CONF_PLANT_NAME: "Mint"})
        await flow.async_step_threshold_source({"method": "openplantbook"})
        instance = mock_client.return_value
    instance.search = AsyncMock(side_effect=RuntimeError)
    await flow.async_step_opb_credentials({"client_id": "id", "secret": "sec"})
    result = await flow.async_step_opb_species_search({"query": "mint"})

    assert result["step_id"] == "thresholds"


async def test_options_flow_add_profile_attach_sensors(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    hass.states.async_set("sensor.temp", 20, {"device_class": "temperature"})
    result = await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})
    assert result["type"] == "form" and result["step_id"] == "attach_sensors"
    assert "sensor.temp" in result["description_placeholders"]["sensor_hints"]
    with (
        patch(
            "custom_components.horticulture_assistant.config_flow._has_registered_service",
            return_value=True,
        ),
        patch.object(hass.services, "async_call", AsyncMock()) as async_call,
    ):
        result2 = await flow.async_step_attach_sensors({"temperature": "sensor.temp"})
        await hass.async_block_till_done()
    assert result2["type"] == "create_entry"
    prof = registry.get_profile("basil")
    assert prof is not None
    assert prof.general[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert prof.general["sensors"]["temperature"] == "sensor.temp"
    dismiss_calls = [
        call
        for call in async_call.call_args_list
        if call.args[0] == "persistent_notification" and call.args[1] == "dismiss"
    ]
    assert any("_link" in call.args[2].get("notification_id", "") for call in dismiss_calls)


async def test_options_flow_attach_sensors_allows_skip(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    result = await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})
    assert result["type"] == "form" and result["step_id"] == "attach_sensors"

    with (
        patch(
            "custom_components.horticulture_assistant.config_flow._has_registered_service",
            return_value=True,
        ),
        patch.object(hass.services, "async_call", AsyncMock()) as async_call,
    ):
        result2 = await flow.async_step_attach_sensors({})
        await hass.async_block_till_done()
    assert result2["type"] == "create_entry"
    profile = registry.get_profile("basil")
    assert profile is not None
    assert profile.general.get("sensors") == {}
    create_calls = [
        call
        for call in async_call.call_args_list
        if call.args[0] == "persistent_notification" and call.args[1] == "create"
    ]
    assert create_calls
    payload = create_calls[-1].args[2]
    assert "Basil" in payload["message"]
    assert payload["notification_id"].endswith("_link")


async def test_options_flow_attach_sensors_conflict_requires_confirmation(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "k"},
        options={
            CONF_PROFILES: {
                "mint": {
                    "name": "Mint",
                    "general": {
                        CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
                        "sensors": {"temperature": "sensor.shared"},
                    },
                    "sensors": {"temperature": "sensor.shared"},
                }
            }
        },
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    hass.states.async_set("sensor.shared", 20, {"device_class": "temperature"})

    conflict = await flow.async_step_attach_sensors({"temperature": "sensor.shared"})
    assert conflict["type"] == "form"
    assert conflict["step_id"] == "attach_sensors"
    warning = conflict["description_placeholders"].get("conflict_warning", "")
    assert "Warning" in warning

    with (
        patch(
            "custom_components.horticulture_assistant.config_flow._has_registered_service",
            return_value=True,
        ),
        patch.object(hass.services, "async_call", AsyncMock()),
    ):
        result = await flow.async_step_attach_sensors({"temperature": "sensor.shared"})
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"


async def test_options_flow_add_profile_requires_known_species(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    result = await flow.async_step_add_profile(
        {"name": "Basil", "species_id": "missing", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"species_id": "unknown_species"}


async def test_options_flow_add_profile_persists_species_selection(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    result = await flow.async_step_add_profile(
        {
            "name": "Basil",
            "species_id": "global_basil",
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
        }
    )
    assert result["type"] == "form" and result["step_id"] == "attach_sensors"

    outcome = await flow.async_step_attach_sensors({})
    assert outcome["type"] == "create_entry"

    profile = registry.get_profile("basil")
    assert profile is not None
    stored = registry.entry.options[CONF_PROFILES]["basil"]
    assert stored.get("species_display")
    local_meta = stored.get("local", {}).get("metadata", {})
    assert local_meta.get("requested_species_id") == "global_basil"


async def test_options_flow_add_profile_accepts_existing_profile_species(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    await registry.async_add_profile(
        "Existing Plant",
        species_id="existing_species",
        species_display="Existing Species",
        cultivar_id="existing_cultivar",
        cultivar_display="Existing Cultivar",
    )

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    result = await flow.async_step_add_profile(
        {
            "name": "Seedling",
            "species_id": "existing_species",
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
        }
    )

    assert result["type"] == "form" and result["step_id"] == "attach_sensors"


async def test_options_flow_add_profile_accepts_profile_store_species(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    store = AsyncMock()
    store.async_list.return_value = ["Library Basil"]
    store.async_get.return_value = {
        "name": "Library Basil",
        "species_display": "Library Basil",
        "local": {"metadata": {"requested_species_id": "library_basil", "requested_cultivar_id": "library_gen"}},
        "cultivar_display": "Library Gen",
        "general": {"cultivar": "Library Gen"},
    }

    with patch.object(flow, "_async_profile_store", AsyncMock(return_value=store)):
        flow._species_catalog = None
        flow._cultivar_index = None
        result = await flow.async_step_add_profile(
            {
                "name": "Library Plant",
                "species_id": "library_basil",
                "cultivar_id": "library_gen",
                CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            }
        )

    assert result["type"] == "form" and result["step_id"] == "attach_sensors"
    store.async_list.assert_awaited()
    store.async_get.assert_awaited()


async def test_options_flow_add_profile_rejects_unknown_cultivar(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    catalog = {
        "global_basil": {
            "label": "Global Basil",
            "payload": {},
            "sources": {"library"},
            "cultivars": {},
        }
    }
    flow._async_species_catalog = AsyncMock(return_value=(catalog, {}))  # type: ignore[method-assign]

    result = await flow.async_step_add_profile(
        {
            "name": "Basil",
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            "cultivar_id": "unknown",
        }
    )

    assert result["type"] == "form"
    assert result["errors"] == {"cultivar_id": "unknown_cultivar"}


async def test_options_flow_add_profile_infers_species_from_cultivar(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    cultivar_entry = {"label": "Genovese Basil", "source": "library", "sources": {"library"}, "payload": {}}
    catalog = {
        "global_basil": {
            "label": "Global Basil",
            "payload": {},
            "sources": {"library"},
            "cultivars": {"basil_genovese": cultivar_entry},
        }
    }
    cultivar_index = {"basil_genovese": ("global_basil", cultivar_entry)}
    flow._async_species_catalog = AsyncMock(  # type: ignore[method-assign]
        return_value=(catalog, cultivar_index)
    )

    result = await flow.async_step_add_profile(
        {
            "name": "Genovese",
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            "cultivar_id": "basil_genovese",
        }
    )

    assert result["type"] == "form" and result["step_id"] == "attach_sensors"

    stored = registry.entry.options[CONF_PROFILES]["genovese"]
    metadata = stored.get("local", {}).get("metadata", {})
    assert metadata.get("requested_species_id") == "global_basil"
    assert metadata.get("requested_cultivar_id") == "basil_genovese"
    assert stored.get("cultivar_display") == "Genovese Basil"
    general = stored.get("general", {})
    assert general.get("cultivar") == "Genovese Basil"


async def test_options_flow_add_profile_species_hint_guidance(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    cultivar_entry = {"label": "Genovese Basil", "sources": {"library"}}
    catalog = {
        "global_basil": {
            "label": "Global Basil",
            "payload": {},
            "sources": {"library"},
            "cultivars": {"basil_genovese": cultivar_entry},
        }
    }
    cultivar_index = {"basil_genovese": ("global_basil", cultivar_entry)}
    flow._async_species_catalog = AsyncMock(  # type: ignore[method-assign]
        return_value=(catalog, cultivar_index)
    )

    result = await flow.async_step_add_profile(
        {
            "name": "",
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            "species_id": "global_basil",
            "cultivar_id": "basil_genovese",
        }
    )

    assert result["type"] == "form"
    placeholders = result.get("description_placeholders")
    assert placeholders is not None
    assert "Species template: Global Basil" in placeholders.get("species_hint", "")
    assert "Library templates" in placeholders.get("species_hint", "")
    assert "Cultivar: Genovese Basil" in placeholders.get("cultivar_hint", "")
    assert "Parent species: Global Basil" in placeholders.get("cultivar_hint", "")


async def test_options_flow_add_profile_species_hint_defaults(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    flow._async_species_catalog = AsyncMock(  # type: ignore[method-assign]
        return_value=({}, {})
    )

    result = await flow.async_step_add_profile({"name": "", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    assert result["type"] == "form"
    placeholders = result.get("description_placeholders")
    assert placeholders is not None
    assert placeholders.get("species_hint") == "No species template selected — profile will rely on manual defaults."
    assert placeholders.get("cultivar_hint") == "No cultivar overrides selected — using the base species defaults."


async def test_options_flow_attach_sensors_validation_errors(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    result = await flow.async_step_attach_sensors({"temperature": "sensor.missing"})
    assert result["type"] == "form"
    assert result["errors"] == {"temperature": "missing_entity"}


async def test_options_flow_add_profile_rejects_duplicate_name(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    await registry.async_add_profile("Basil")

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    result = await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    assert result["type"] == "form"
    assert result["errors"] == {"name": "duplicate_profile_id"}


async def test_options_flow_add_profile_invalid_name(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    result = await flow.async_step_add_profile({"name": "!!!", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    assert result["type"] == "form"
    assert result["errors"] == {"name": "invalid_profile_id"}


async def test_options_flow_add_profile_persist_failure_rolls_back(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    from custom_components.horticulture_assistant.profile_store import ProfileStoreError

    store = AsyncMock()
    store.async_create_profile.side_effect = ProfileStoreError("write failed", user_message="disk full")

    with patch(
        "custom_components.horticulture_assistant.config_flow.get_entry_data",
        return_value={"profile_store": store},
    ):
        result = await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "profile_error"}
    assert result["description_placeholders"]["error"] == "disk full"
    assert registry.get_profile("basil") is None


async def test_options_flow_add_profile_registry_save_error(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "k"})
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()

    with patch.object(registry, "async_save", AsyncMock(side_effect=OSError("disk full"))):
        result = await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})

    assert result["type"] == "form"
    assert result["errors"] == {"base": "profile_error"}
    assert registry.get_profile("basil") is None
    assert entry.options.get(CONF_PROFILES, {}) == {}


async def test_options_flow_sensor_warning_skips_missing_notification_service(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    flow = OptionsFlow(entry)
    flow.hass = hass

    async def unexpected_call(*args, **kwargs):
        raise AssertionError("notification service should not be invoked")

    hass.services = types.SimpleNamespace(async_call=unexpected_call)

    with (
        patch.object(
            hass,
            "async_create_task",
            side_effect=AssertionError("notification task should not be scheduled"),
        ) as create_task,
        patch("custom_components.horticulture_assistant.config_flow.collate_issue_messages") as collate,
    ):
        flow._notify_sensor_warnings([object()])

    collate.assert_not_called()
    create_task.assert_not_called()


async def test_options_flow_sensor_warning_creates_notification_when_service_available(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    flow = OptionsFlow(entry)
    flow.hass = hass

    class FakeServices:
        def __init__(self):
            self.calls: list[tuple[str, str, dict[str, str], bool]] = []
            self._services = {"persistent_notification": {"create": object()}}

        async def async_call(self, domain: str, service: str, data: dict[str, str], *, blocking: bool = False) -> None:
            self.calls.append((domain, service, data, blocking))

    services = FakeServices()
    hass.services = services

    with (
        patch(
            "custom_components.horticulture_assistant.config_flow.collate_issue_messages",
            return_value="warning",
        ) as collate,
    ):
        flow._notify_sensor_warnings([object()])

    await asyncio.sleep(0)

    collate.assert_called_once()
    assert services.calls == [
        (
            "persistent_notification",
            "create",
            {
                "title": "Horticulture Assistant sensor warning",
                "message": "warning",
                "notification_id": f"horticulture_sensor_{entry.entry_id}",
            },
            False,
        )
    ]


async def test_options_flow_manage_profile_general_updates_profile(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT, "plant_type": "herb"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_general"})
    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry):
        result = await flow.async_step_manage_profile_general(
            {
                "name": "Renamed Plant",
                CONF_PROFILE_SCOPE: "grow_zone",
                "plant_type": "",
                "species_display": "Mentha",
            }
        )

    assert result["type"] == "create_entry"
    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["name"] == "Renamed Plant"
    assert stored["general"][CONF_PROFILE_SCOPE] == "grow_zone"
    assert "plant_type" not in stored["general"]
    assert stored["species_display"] == "Mentha"


async def test_options_flow_manage_profile_sensors_validates_and_updates(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT, "sensors": {"temperature": "sensor.old"}},
        "sensors": {"temperature": "sensor.old"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    hass.states.async_set("sensor.temp_new", 25, {"device_class": "temperature"})
    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_sensors"})
    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry):
        result = await flow.async_step_manage_profile_sensors({"temperature": "sensor.temp_new", "humidity": ""})

    assert result["type"] == "create_entry"
    stored = entry.options[CONF_PROFILES]["alpha"]
    sensors = stored["general"].get("sensors", {})
    assert sensors == {"temperature": "sensor.temp_new"}


async def test_options_flow_manage_profile_sensors_preserves_multi_assignments(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            "sensors": {"temperature": ["sensor.temp_a", "sensor.temp_b"]},
        },
        "sensors": {"temperature": ["sensor.temp_a", "sensor.temp_b"]},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    hass.states.async_set("sensor.temp_a", 20, {"device_class": "temperature"})
    hass.states.async_set("sensor.temp_b", 21, {"device_class": "temperature"})

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_sensors"})
    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry):
        result = await flow.async_step_manage_profile_sensors({"temperature": ["sensor.temp_a", "sensor.temp_b"]})

    assert result["type"] == "create_entry"
    stored = entry.options[CONF_PROFILES]["alpha"]
    sensors = stored["general"].get("sensors", {})
    assert sensors == {"temperature": ["sensor.temp_a", "sensor.temp_b"]}


async def test_options_flow_manage_profile_sensors_includes_hints(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_sensors"})

    suggestions = {role: [] for role in ("temperature", "humidity", "illuminance", "moisture", "conductivity", "co2")}
    suggestions["temperature"] = [SensorSuggestion("sensor.tent_temp", "Grow Tent Temp", 6, "matched")]

    with patch(
        "custom_components.horticulture_assistant.config_flow.collect_sensor_suggestions",
        return_value=suggestions,
    ):
        result = await flow.async_step_manage_profile_sensors()

    assert result["type"] == "form"
    hints = result["description_placeholders"]["sensor_hints"]
    assert "Grow Tent Temp (sensor.tent_temp)" in hints


async def test_options_flow_manage_profile_sensors_conflict_requires_confirmation(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
        "sensors": {},
    }
    conflict_payload = {
        "name": "Beta",
        "general": {
            CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT,
            "sensors": {"temperature": "sensor.shared"},
        },
        "sensors": {"temperature": "sensor.shared"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload, "beta": conflict_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    hass.states.async_set("sensor.shared", 21, {"device_class": "temperature"})

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_sensors"})
    conflict = await flow.async_step_manage_profile_sensors({"temperature": "sensor.shared"})
    assert conflict["type"] == "form"
    assert "Warning" in conflict["description_placeholders"].get("conflict_warning", "")

    def _update_entry(target, *, options):
        target.options = options

    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry):
        result = await flow.async_step_manage_profile_sensors({"temperature": "sensor.shared"})

    assert result["type"] == "create_entry"


async def test_options_flow_manage_profile_sensors_handles_validation_errors(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_sensors"})

    validation = SensorValidationResult(
        errors=[
            SensorValidationIssue(
                role="temperature",
                entity_id="sensor.missing",
                issue="missing_entity",
                severity="error",
            )
        ],
        warnings=[],
    )

    with (
        patch(
            "custom_components.horticulture_assistant.config_flow.collect_sensor_suggestions",
            return_value={},
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.validate_sensor_links",
            return_value=validation,
        ),
        patch.object(flow, "_clear_sensor_warning") as clear_warning,
        patch.object(registry, "async_set_profile_sensors", new=AsyncMock()) as set_sensors,
    ):
        result = await flow.async_step_manage_profile_sensors({"temperature": "sensor.missing"})

    assert result["type"] == "form"
    assert result["errors"]["temperature"] == "missing_entity"
    assert result["errors"]["base"] == "sensor_validation_failed"
    assert "missing_entity" in result["description_placeholders"]["error"]
    set_sensors.assert_not_called()
    clear_warning.assert_called_once()


async def test_options_flow_manage_profile_sensors_notifies_warnings(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_sensors"})

    validation = SensorValidationResult(
        errors=[],
        warnings=[
            SensorValidationIssue(
                role="temperature",
                entity_id="sensor.flagged",
                issue="unexpected_device_class",
                severity="warning",
                expected="temperature",
                observed="humidity",
            )
        ],
    )

    with (
        patch(
            "custom_components.horticulture_assistant.config_flow.collect_sensor_suggestions",
            return_value={},
        ),
        patch(
            "custom_components.horticulture_assistant.config_flow.validate_sensor_links",
            return_value=validation,
        ),
        patch.object(flow, "_notify_sensor_warnings") as notify_warnings,
        patch.object(flow, "_clear_sensor_warning") as clear_warning,
        patch.object(registry, "async_set_profile_sensors", new=AsyncMock()) as set_sensors,
    ):
        result = await flow.async_step_manage_profile_sensors({"temperature": "sensor.flagged"})

    notify_warnings.assert_called_once()
    clear_warning.assert_not_called()
    set_sensors.assert_awaited_once()
    assert result["type"] == "create_entry"


async def test_options_flow_manage_profile_thresholds_updates_targets(hass):
    profile_payload = {
        "name": "Alpha",
        "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT},
        "thresholds": {
            "temperature_min": 16.0,
            "temperature_max": 24.0,
            "humidity_min": 40.0,
        },
    }
    sync_thresholds(profile_payload)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "edit_thresholds"})
    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry):
        result = await flow.async_step_manage_profile_thresholds(
            {
                "temperature_min": "18.5",
                "temperature_max": "25.5",
                "humidity_min": "",
                "humidity_max": "",
                "illuminance_min": "",
                "illuminance_max": "",
                "conductivity_min": "",
                "conductivity_max": "",
            }
        )

    assert result["type"] == "create_entry"
    stored = entry.options[CONF_PROFILES]["alpha"]
    assert stored["thresholds"]["temperature_min"] == pytest.approx(18.5)
    assert stored["thresholds"]["temperature_max"] == pytest.approx(25.5)
    assert "humidity_min" not in stored["thresholds"]
    assert stored["resolved_targets"]["temperature_min"]["value"] == pytest.approx(18.5)
    assert stored["resolved_targets"]["temperature_max"]["value"] == pytest.approx(25.5)


async def test_options_flow_manage_profile_delete_blocks_primary(hass):
    profile_payload = {"name": "Alpha", "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT}}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PLANT_ID: "alpha"},
        options={CONF_PROFILES: {"alpha": profile_payload}},
    )
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_manage_profiles({"profile_id": "alpha", "action": "delete"})
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_delete_primary"


async def test_options_flow_manage_profile_delete_secondary(hass):
    options = {
        CONF_PROFILES: {
            "alpha": {"name": "Primary", "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT}},
            "beta": {"name": "Secondary", "general": {CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT}},
        }
    }
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_PLANT_ID: "alpha"}, options=options)
    entry.add_to_hass(hass)
    registry = ProfileRegistry(hass, entry)
    await registry.async_load()
    hass.data.setdefault(DOMAIN, {})["registry"] = registry

    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    await flow.async_step_manage_profiles({"profile_id": "beta", "action": "delete"})
    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry):
        result = await flow.async_step_manage_profile_delete({"confirm": True})

    assert result["type"] == "create_entry"
    assert "beta" not in entry.options[CONF_PROFILES]


async def test_options_flow_manual_nutrient_schedule(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "profiles": {
                "plant": {
                    "name": "Demo plant",
                    "general": {"plant_type": "citrus"},
                    "local": {"general": {"plant_type": "citrus"}},
                }
            }
        },
    )
    entry.add_to_hass(hass)
    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    await flow.async_step_nutrient_schedule({"profile_id": "plant"})
    schedule_json = json.dumps([{"stage": "veg", "duration_days": 14, "totals": {"N": 280}}])
    with patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry) as update_mock:
        result = await flow.async_step_nutrient_schedule_edit({"schedule": schedule_json})
    assert result["type"] == "create_entry"
    update_mock.assert_called()
    stored = entry.options["profiles"]["plant"]["local"]["general"]["nutrient_schedule"]
    assert len(stored) == 1
    assert stored[0]["stage"] == "veg"
    assert stored[0]["duration_days"] == 14
    assert stored[0]["totals_mg"]["N"] == pytest.approx(280.0)
    assert stored[0]["daily_mg"]["N"] == pytest.approx(20.0)


async def test_options_flow_auto_generate_nutrient_schedule(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "profiles": {
                "plant": {
                    "name": "Demo plant",
                    "general": {"plant_type": "citrus"},
                    "local": {"general": {"plant_type": "citrus"}},
                }
            }
        },
    )
    entry.add_to_hass(hass)
    flow = OptionsFlow(entry)
    flow.hass = hass

    def _update_entry(target, *, options):
        target.options = options

    await flow.async_step_nutrient_schedule({"profile_id": "plant"})
    fake_stage = types.SimpleNamespace(stage="flower", duration_days=10, totals={"N": 100, "K": 150})
    with (
        patch.object(hass.config_entries, "async_update_entry", side_effect=_update_entry) as update_mock,
        patch.object(cfg, "generate_nutrient_schedule", return_value=[fake_stage]),
    ):
        result = await flow.async_step_nutrient_schedule_edit({"auto_generate": True})
    assert result["type"] == "create_entry"
    update_mock.assert_called()
    stored = entry.options["profiles"]["plant"]["general"]["nutrient_schedule"]
    assert stored[0]["source"] == "auto_generate"
    assert stored[0]["stage"] == "flower"
    assert stored[0]["daily_mg"]["N"] == pytest.approx(10.0)
    assert stored[0]["start_day"] == 1
    assert stored[0]["end_day"] == 10


async def test_options_flow_invalid_schedule_input(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "profiles": {
                "plant": {
                    "name": "Demo plant",
                    "general": {"plant_type": "citrus"},
                    "local": {"general": {"plant_type": "citrus"}},
                }
            }
        },
    )
    entry.add_to_hass(hass)
    flow = OptionsFlow(entry)
    flow.hass = hass

    result = await flow.async_step_nutrient_schedule({"profile_id": "plant"})
    assert result["type"] == "form"
    invalid = await flow.async_step_nutrient_schedule_edit({"schedule": "{"})
    assert invalid["type"] == "form"
    assert invalid["errors"]["schedule"] == "invalid_json"
