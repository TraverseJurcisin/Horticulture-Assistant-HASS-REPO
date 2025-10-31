import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

ConfigFlow = cfg.ConfigFlow
OptionsFlow = cfg.OptionsFlow
ProfileRegistry = reg.ProfileRegistry
sync_thresholds = compat.sync_thresholds

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


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


async def test_config_flow_profile_error(hass):
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
    assert result["errors"] == {"base": "profile_error"}


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
    result = await flow.async_step_add_profile({"name": "Basil", CONF_PROFILE_SCOPE: PROFILE_SCOPE_DEFAULT})
    assert result["type"] == "form" and result["step_id"] == "attach_sensors"
    hass.states.async_set("sensor.temp", 20, {"device_class": "temperature"})
    result2 = await flow.async_step_attach_sensors({"temperature": "sensor.temp"})
    assert result2["type"] == "create_entry"
    prof = registry.get_profile("basil")
    assert prof is not None
    assert prof.general[CONF_PROFILE_SCOPE] == PROFILE_SCOPE_DEFAULT
    assert prof.general["sensors"]["temperature"] == "sensor.temp"


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

    result2 = await flow.async_step_attach_sensors({})
    assert result2["type"] == "create_entry"
    profile = registry.get_profile("basil")
    assert profile is not None
    assert profile.general.get("sensors") == {}


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
