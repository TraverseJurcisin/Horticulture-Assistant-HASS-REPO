from custom_components.horticulture_assistant.profile.schema import (
    Citation,
    FieldAnnotation,
    PlantProfile,
    ResolvedTarget,
)


def _make_profile():
    return PlantProfile(
        plant_id="p1",
        display_name="Plant",
        species="Avocado",
        resolved_targets={
            "temp": ResolvedTarget(
                value=20,
                annotation=FieldAnnotation(source_type="manual"),
            ),
            "rh": ResolvedTarget(
                value=50,
                annotation=FieldAnnotation(source_type="manual"),
            ),
        },
        general={"note": "test"},
        citations=[Citation(source="manual", title="none")],
    )


def test_summary_basic_fields():
    prof = _make_profile()
    summary = prof.summary()
    assert summary["plant_id"] == "p1"
    assert summary["name"] == "Plant"
    assert summary["species"] == "Avocado"


def test_summary_variables_contain_values_only():
    prof = _make_profile()
    summary = prof.summary()
    assert summary["targets"] == {"temp": 20, "rh": 50}


def test_summary_immutable(hass):  # noqa: ARG001 - hass unused but provided
    """Ensure modifying summary does not affect original profile."""

    prof = _make_profile()
    summary = prof.summary()
    summary["targets"]["temp"] = 30
    assert prof.resolved_targets["temp"].value == 20


def test_summary_without_variables():
    prof = PlantProfile(plant_id="p2", display_name="Empty")
    summary = prof.summary()
    assert summary["targets"] == {}


def test_summary_handles_none_species():
    prof = PlantProfile(plant_id="p3", display_name="NoSpec", species=None)
    summary = prof.summary()
    assert "species" in summary and summary["species"] is None


def test_summary_excludes_general_and_citations():
    prof = _make_profile()
    summary = prof.summary()
    assert "note" not in summary
    assert "citations" not in summary


def test_summary_returns_fresh_copy_each_call():
    prof = _make_profile()
    s1 = prof.summary()
    s2 = prof.summary()
    s1["targets"]["temp"] = 99
    assert s2["targets"]["temp"] == 20


def test_to_json_includes_legacy_views():
    prof = _make_profile()
    payload = prof.to_json()
    assert payload["thresholds"] == {"temp": 20, "rh": 50}
    assert payload["variables"]["temp"]["value"] == 20
    assert payload["variables"]["temp"]["source"] == "manual"


def test_from_json_thresholds_fallback():
    data = {
        "plant_id": "p4",
        "display_name": "Legacy",
        "thresholds": {"temp": 12.5},
    }
    prof = PlantProfile.from_json(data)
    assert prof.resolved_targets["temp"].value == 12.5
    assert prof.resolved_targets["temp"].annotation.source_type == "unknown"
