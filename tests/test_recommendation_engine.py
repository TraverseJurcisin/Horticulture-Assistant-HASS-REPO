import importlib

import pytest


def _import_module():
    return importlib.import_module("custom_components.horticulture_assistant.utils.recommendation_engine")


def test_recommendation_engine_dataclasses_and_defaults():
    module = _import_module()

    fert = module.FertilizerRecommendation(
        product_name="Product X",
        dose_rate=1.5,
        dose_unit="ppm",
        reason="nitrogen deficit",
        severity="medium",
    )
    irrigation = module.IrrigationRecommendation(
        volume_liters=2.0,
        zones=["zone-1"],
        justification="Soil moisture below threshold",
    )
    environment = module.EnvironmentRecommendation(
        adjustments={"temperature": "increase"},
        setpoints={"temperature": 24.0},
    )

    bundle = module.RecommendationBundle(
        fertilizers=[fert],
        irrigation=irrigation,
        environment=environment,
        notes=["Note"],
        requires_approval=True,
    )

    assert bundle.fertilizers[0].product_name == "Product X"
    assert bundle.irrigation.justification.startswith("Soil moisture")
    assert bundle.environment.setpoints["temperature"] == 24.0

    engine = module.RecommendationEngine()
    assert engine.recommend_all() == {}


@pytest.mark.asyncio
async def test_recommendation_engine_handles_string_sensor_values(monkeypatch):
    module = _import_module()

    engine = module.RecommendationEngine()
    engine.update_plant_profile(
        "plant-1",
        {
            "plant_type": "tomato",
            "lifecycle_stage": "vegetative",
            "min_vwc": "30",
            "zones": ["zone-1"],
        },
    )
    engine.update_sensor_data("plant-1", {"vwc": "25"})

    monkeypatch.setattr(
        module.RecommendationEngine,
        "_generate_fertilizer_recs",
        lambda self, pid: [],
    )
    monkeypatch.setattr(
        module.RecommendationEngine,
        "_generate_environment_recs",
        lambda self, pid: None,
    )
    monkeypatch.setattr(
        module.RecommendationEngine,
        "_get_irrigation_target",
        lambda self, plant_type, stage: 1200.0,
    )

    result = engine.recommend("plant-1")

    assert result.irrigation is not None
    assert pytest.approx(result.irrigation.volume_liters) == 1.2
    assert result.irrigation.zones == ["zone-1"]
