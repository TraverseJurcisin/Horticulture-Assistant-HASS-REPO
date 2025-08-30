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

cfg_spec = importlib.util.spec_from_file_location(
    f"{PACKAGE}.config_flow", BASE_PATH / "config_flow.py"
)
cfg = importlib.util.module_from_spec(cfg_spec)
sys.modules[cfg_spec.name] = cfg
cfg_spec.loader.exec_module(cfg)

ConfigFlow = cfg.ConfigFlow
OptionsFlow = cfg.OptionsFlow

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.usefixtures("enable_custom_integrations"),
]


@pytest.fixture(autouse=True)
def _mock_socket():
    with patch("socket.socket") as mock_socket:
        instance = MagicMock()

        def connect(*args, **kwargs):
            if not instance.setblocking.called or instance.setblocking.call_args[0][0] is not False:
                raise ValueError("the socket must be non-blocking")

        instance.connect.side_effect = connect
        mock_socket.return_value = instance
        with patch(
            "socket.create_connection",
            side_effect=ValueError("the socket must be non-blocking"),
        ):
            yield


async def test_config_flow_user(hass):
    """Test user config flow."""
    flow = ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == "form"
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        result2 = await flow.async_step_user({CONF_API_KEY: "abc"})
    assert result2["type"] == "form"
    assert result2["step_id"] == "profile"

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
            }
        )
        assert result3["type"] == "form"
        assert result3["step_id"] == "threshold_source"
        result4 = await flow.async_step_threshold_source({"method": "manual"})
        assert result4["type"] == "form"
        assert result4["step_id"] == "thresholds"
        result4 = await flow.async_step_thresholds({})
        assert result4["type"] == "form"
        assert result4["step_id"] == "sensors"
        hass.states.async_set("sensor.good", 0)
        result5 = await flow.async_step_sensors({"moisture_sensor": "sensor.good"})
    assert result5["type"] == "create_entry"
    assert result5["data"][CONF_PLANT_NAME] == "Mint"
    assert result5["data"][CONF_PLANT_ID] == "mint"
    assert result5["options"] == {
        "moisture_sensor": "sensor.good",
        "sensors": {"moisture": "sensor.good"},
        "thresholds": {},
    }
    assert exec_mock.call_count == 3
    gen_mock.assert_called_once()
    general = json.loads(Path(hass.config.path("plants", "mint", "general.json")).read_text())
    assert general["sensor_entities"] == {"moisture_sensors": ["sensor.good"]}
    assert general["plant_type"] == "herb"
    registry = json.loads(
        Path(hass.config.path("data", "local", "plants", "plant_registry.json")).read_text()
    )
    assert registry["mint"]["display_name"] == "Mint"
    assert registry["mint"]["plant_type"] == "Herb"


async def test_config_flow_invalid_key(hass):
    """Test config flow handles invalid API key."""
    flow = ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user()
    assert result["type"] == "form"
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        side_effect=Exception,
    ):
        result2 = await flow.async_step_user({CONF_API_KEY: "bad"})
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_config_flow_profile_error(hass):
    flow = ConfigFlow()
    flow.hass = hass
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

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
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})
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
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

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
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

    async def _run(func, *args):
        return func(*args)

    with patch.object(hass, "async_add_executor_job", side_effect=_run):
        await flow.async_step_profile({CONF_PLANT_NAME: "Rose"})
        await flow.async_step_threshold_source({"method": "manual"})
        result_th = await flow.async_step_thresholds({})
        assert result_th["type"] == "form" and result_th["step_id"] == "sensors"
        result = await flow.async_step_sensors({})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_PLANT_NAME] == "Rose"
    assert result["data"][CONF_PLANT_ID] == "rose"
    assert result["options"] == {"sensors": {}, "thresholds": {}}
    general = json.loads(Path(hass.config.path("plants", "rose", "general.json")).read_text())
    sensors = general.get("sensor_entities", {})
    assert all(not values for values in sensors.values())
    registry = json.loads(
        Path(hass.config.path("data", "local", "plants", "plant_registry.json")).read_text()
    )
    assert registry["rose"]["display_name"] == "Rose"
    assert "plant_type" not in registry["rose"]
    assert general["plant_type"] == "TBD"


async def test_options_flow(hass, hass_admin_user):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, title="title")
    flow = OptionsFlow(entry)
    flow.hass = hass
    await flow.async_step_init()
    result = await flow.async_step_basic()
    assert result["type"] == "form"
    result2 = await flow.async_step_basic({})
    assert result2["type"] == "create_entry"


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
    (profile_dir / "general.json").write_text(
        json.dumps({"sensor_entities": {"moisture_sensors": ["sensor.old"]}})
    )

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
    await flow.async_step_user()
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

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
    assert result["options"]["image_url"] == "/local/mint.jpg"
    assert result["options"]["species_pid"] == "pid123"
    assert result["options"]["opb_credentials"] == {"client_id": "id", "secret": "sec"}


async def test_config_flow_openplantbook_no_auto_download(hass):
    flow = ConfigFlow()
    flow.hass = hass
    await flow.async_step_user()
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

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
    await flow.async_step_user()
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

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
    await flow.async_step_user()
    with patch(
        "custom_components.horticulture_assistant.config_flow.ChatApi.validate_api_key",
        return_value=None,
    ):
        await flow.async_step_user({CONF_API_KEY: "abc"})

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
