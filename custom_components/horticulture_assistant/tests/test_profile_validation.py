from ..utils import bio_profile_loader as loader


def test_validate_profile_complete():
    profile = {
        "plant_id": "p1",
        "display_name": "Plant 1",
        "stage": "seedling",
        "general": {"sensor_entities": {"moisture": "s1"}},
    }
    assert loader.validate_profile(profile) == []


def test_validate_profile_missing():
    profile = {"plant_id": "p1"}
    missing = loader.validate_profile(profile)
    assert "display_name" in missing
    assert "stage" in missing
    assert "sensor_entities" in missing
