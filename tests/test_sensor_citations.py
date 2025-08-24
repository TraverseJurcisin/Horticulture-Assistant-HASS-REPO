import logging
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.horticulture_assistant.sensor import HortiStatusSensor


@pytest.mark.asyncio
async def test_status_sensor_citation_summary(hass: HomeAssistant):
    profile = {
        "plant_id": "p1",
        "display_name": "Plant 1",
        "last_resolved": "2024-01-02T00:00:00+00:00",
        "variables": {
            "air_temp_min": {
                "value": 10,
                "source": "manual",
                "citations": [{"source": "manual", "title": "note", "url": "http://a"}],
            },
            "air_temp_max": {
                "value": 20,
                "source": "manual",
                "citations": [
                    {"source": "clone", "title": "", "url": "http://b"},
                    {"source": "manual", "title": "", "url": "http://c"},
                    {"source": "manual", "title": "", "url": "http://b"},
                ],
            },
        },
    }
    coord = DataUpdateCoordinator(
        hass, logging.getLogger(__name__), name="ai", update_interval=None
    )
    coord.async_set_updated_data({"ok": True})
    local = DataUpdateCoordinator(
        hass, logging.getLogger(__name__), name="local", update_interval=None
    )

    with patch(
        "custom_components.horticulture_assistant.profile.store.async_load_all",
        return_value={"p1": profile},
    ):
        sensor = HortiStatusSensor(coord, local, "entry", keep_stale=True)
        sensor.hass = hass
        await sensor.async_added_to_hass()

    attrs = sensor.extra_state_attributes
    assert attrs["citations_count"] == 4
    assert attrs["citations_summary"] == {
        "air_temp_min": 1,
        "air_temp_max": 3,
    }
    assert attrs["citations_links_preview"] == ["http://a", "http://b", "http://c"]
    assert attrs["last_resolved_utc"] == "2024-01-02T00:00:00+00:00"
