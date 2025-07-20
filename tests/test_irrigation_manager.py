from plant_engine.irrigation_manager import recommend_irrigation_volume
from plant_engine.rootzone_model import RootZone


def test_recommend_irrigation_volume_basic():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    # After ET, projected volume below RAW so refill to full
    vol = recommend_irrigation_volume(zone, available_ml=120.0, expected_et_ml=40.0)
    assert vol == 120.0


def test_irrigation_no_action_when_sufficient():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    vol = recommend_irrigation_volume(zone, available_ml=150.0, expected_et_ml=30.0)
    assert vol == 0.0

