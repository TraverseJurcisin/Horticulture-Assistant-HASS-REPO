import os
import sys
import types
from pathlib import Path

import pytest

from tests import conftest as _shared_conftest  # ensure shared stubs are registered  # noqa: F401

# Stub aiohttp and minimal Home Assistant modules used during CLI tests.

aiohttp_stub = types.ModuleType("aiohttp")

aiohttp_stub.ClientError = Exception

aiohttp_stub.ClientResponseError = Exception

sys.modules.setdefault("aiohttp", aiohttp_stub)



components_stub = sys.modules.setdefault(

    "homeassistant.components", types.ModuleType("homeassistant.components")

)



sensor_stub = sys.modules.setdefault(

    "homeassistant.components.sensor", types.ModuleType("homeassistant.components.sensor")

)

if not hasattr(sensor_stub, "SensorDeviceClass"):

    sensor_stub.SensorDeviceClass = type(

        "SensorDeviceClass",

        (),

        {

            "TEMPERATURE": "temperature",

            "HUMIDITY": "humidity",

            "ILLUMINANCE": "illuminance",

            "MOISTURE": "moisture",

        },

    )

if not hasattr(sensor_stub, "SensorEntity"):

    sensor_stub.SensorEntity = type("SensorEntity", (), {})

if not hasattr(sensor_stub, "SensorStateClass"):

    sensor_stub.SensorStateClass = type(

        "SensorStateClass",

        (),

        {"MEASUREMENT": "measurement"},

    )



core_stub = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))

core_stub.HomeAssistant = getattr(core_stub, "HomeAssistant", type("HomeAssistant", (), {}))

core_stub.callback = getattr(core_stub, "callback", (lambda func: func))



helpers_event_stub = sys.modules.setdefault(

    "homeassistant.helpers.event", types.ModuleType("homeassistant.helpers.event")

)

if not hasattr(helpers_event_stub, "async_track_state_change_event"):

    helpers_event_stub.async_track_state_change_event = lambda *args, **kwargs: None



helpers_entity_stub = sys.modules.setdefault(

    "homeassistant.helpers.entity", types.ModuleType("homeassistant.helpers.entity")

)

if not hasattr(helpers_entity_stub, "Entity"):

    helpers_entity_stub.Entity = type("Entity", (), {})



# Ensure project root is on path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(0, str(ROOT))



# Ensure the bundled dataset is discoverable before configuring optional locations.

os.environ.setdefault("HORTICULTURE_DATA_DIR", str(ROOT / "data"))



# Default dataset locations – fall back to the bundled fertilizer dataset if

# external feature data is not present.

feature_index = ROOT / "feature/fertilizer_dataset_sharded/index_sharded"

feature_detail = ROOT / "feature/fertilizer_dataset_sharded/detail"

bundled_index = ROOT / "data/fertilizers/index_sharded"

bundled_detail = ROOT / "data/fertilizers/detail"



index_dir = Path(os.environ.setdefault("FERTILIZER_DATASET_INDEX_DIR", str(feature_index)))

detail_dir = Path(os.environ.setdefault("FERTILIZER_DATASET_DETAIL_DIR", str(feature_detail)))



if not index_dir.exists() and bundled_index.exists():

    os.environ["FERTILIZER_DATASET_INDEX_DIR"] = str(bundled_index)

    index_dir = bundled_index

if not detail_dir.exists() and bundled_detail.exists():

    os.environ["FERTILIZER_DATASET_DETAIL_DIR"] = str(bundled_detail)

    detail_dir = bundled_detail



# Detect optional dataset availability. Many CLI and fertilizer dataset tests

# rely on large reference datasets that are not included in this trimmed repository.

HAS_LOCAL_DATA = (ROOT / "data" / "local").exists()

HAS_FERTILIZER_DATASET = index_dir.exists()





def pytest_collection_modifyitems(config, items):

    """Automatically skip tests that require missing datasets."""



    skip_local = pytest.mark.skip(reason="requires local datasets")

    skip_fertilizer = pytest.mark.skip(reason="requires fertilizer dataset")



    for item in items:

        name = item.fspath.basename

        nodeid = item.nodeid

        if "fertilizer" in name.lower() and not HAS_FERTILIZER_DATASET:

            item.add_marker(skip_fertilizer)

        elif ("script" in name.lower() or "dataset" in nodeid) and not HAS_LOCAL_DATA:

            item.add_marker(skip_local)

