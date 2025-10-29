from custom_components.horticulture_assistant.profile.schema import (
    ProfileLibrarySection,
    ProfileLocalSection,
)
from custom_components.horticulture_assistant.profile.utils import (
    determine_species_slug,
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


def test_normalise_profile_payload_prefers_profile_id_for_missing_plant_id() -> None:
    payload = {"profile_id": "existing", "display_name": "My Plant"}

    normalised = normalise_profile_payload(payload, fallback_id="generated", display_name="My Plant")

    assert normalised["profile_id"] == "existing"
    assert normalised["plant_id"] == "existing"


def test_determine_species_slug_ignores_whitespace_candidates() -> None:
    library = ProfileLibrarySection(profile_id="lib-1", identity={"species": "  Pisum sativum  "})
    local = ProfileLocalSection(species="   ")

    slug = determine_species_slug(library=library, local=local, raw="   ")

    assert slug == "Pisum sativum"


def test_determine_species_slug_returns_none_for_blank_values() -> None:
    assert determine_species_slug(raw="   ") is None
    assert (
        determine_species_slug(
            raw={"slug": "   ", "taxonomy": {"species": "   "}},
        )
        is None
    )
