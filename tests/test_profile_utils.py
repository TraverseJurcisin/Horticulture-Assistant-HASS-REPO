from custom_components.horticulture_assistant.profile.utils import (
    ensure_sections,
    normalise_profile_payload,
    sync_general_section,
)


def test_sync_general_section_updates_structured_sections() -> None:
    payload: dict[str, object] = {"plant_id": "p1", "name": "Plant"}
    ensure_sections(payload, plant_id="p1", display_name="Plant")

    sync_general_section(payload, {"sensors": {"temp": "sensor.one"}, "note": "local"})

    assert payload["general"]["sensors"]["temp"] == "sensor.one"
    assert payload["local"]["general"]["sensors"]["temp"] == "sensor.one"
    assert payload["sections"]["local"]["general"]["sensors"]["temp"] == "sensor.one"


def test_ensure_sections_falls_back_to_generated_identifiers() -> None:
    payload: dict[str, object] = {"plant_id": " ", "profile_id": "", "display_name": "   "}

    ensure_sections(payload, plant_id="", display_name=" ")

    assert payload["plant_id"] == "profile"
    assert payload["profile_id"] == "profile"
    assert payload["display_name"] == "profile"


def test_normalise_profile_payload_falls_back_to_generated_identifiers() -> None:
    payload = {"plant_id": "", "profile_id": " ", "display_name": "   "}

    normalised = normalise_profile_payload(payload)

    assert normalised["plant_id"] == "profile"
    assert normalised["profile_id"] == "profile"
    assert normalised["display_name"] == "profile"
