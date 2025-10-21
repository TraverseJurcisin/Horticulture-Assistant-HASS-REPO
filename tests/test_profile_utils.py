from custom_components.horticulture_assistant.profile.utils import (
    ensure_sections,
    sync_general_section,
)


def test_sync_general_section_updates_structured_sections() -> None:
    payload: dict[str, object] = {"plant_id": "p1", "name": "Plant"}
    ensure_sections(payload, plant_id="p1", display_name="Plant")

    sync_general_section(payload, {"sensors": {"temp": "sensor.one"}, "note": "local"})

    assert payload["general"]["sensors"]["temp"] == "sensor.one"
    assert payload["local"]["general"]["sensors"]["temp"] == "sensor.one"
    assert payload["sections"]["local"]["general"]["sensors"]["temp"] == "sensor.one"
