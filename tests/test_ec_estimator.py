import json
from custom_components.horticulture_assistant.utils import ec_estimator


def test_train_and_estimate(tmp_path):
    samples = [
        {
            "moisture": 30,
            "temperature": 20,
            "irrigation_ml": 100,
            "solution_ec": 1.2,
            "humidity": 55,
            "observed_ec": 1.0,
        },
        {
            "moisture": 40,
            "temperature": 22,
            "irrigation_ml": 150,
            "solution_ec": 1.5,
            "humidity": 60,
            "observed_ec": 1.4,
        },
        {
            "moisture": 35,
            "temperature": 21,
            "irrigation_ml": 120,
            "solution_ec": 1.3,
            "humidity": 57,
            "observed_ec": 1.2,
        },
    ]
    model = ec_estimator.train_ec_model(
        samples,
        plant_id="plant1",
        base_path=tmp_path,
    )
    model_file = tmp_path / "plant1" / "ec_model.json"
    assert model_file.exists()

    est = ec_estimator.estimate_ec_from_values(
        36,
        21,
        130,
        1.4,
        model=model,
        extra_features={"humidity": 58},
    )
    assert isinstance(est, float)


def test_log_runoff(tmp_path):
    ec_estimator.log_runoff_ec("plant1", 1.5, base_path=tmp_path)
    log = tmp_path / "plant1" / "runoff_ec_log.json"
    assert log.exists()
    data = json.loads(log.read_text())
    assert data and data[0]["ec"] == 1.5


def test_default_model_dataset(tmp_path):
    """Model loads defaults from bundled dataset when file missing."""

    model = ec_estimator.load_model(base_path=tmp_path)
    assert isinstance(model, ec_estimator.ECEstimator)
    assert model.intercept == 0.0
    assert "moisture" in model.coeffs


def test_load_model_cache(tmp_path):
    """Cached model is reused until cache is cleared."""

    path = tmp_path / "model.json"
    path.write_text(json.dumps({"intercept": 1, "coeffs": {"moisture": 0.1}}))
    m1 = ec_estimator.load_model(path)
    path.write_text(json.dumps({"intercept": 2, "coeffs": {"moisture": 0.2}}))
    m2 = ec_estimator.load_model(path)
    assert m1 is m2  # cached instance
    ec_estimator.clear_model_cache()
    m3 = ec_estimator.load_model(path)
    assert m3.intercept == 2


def test_estimate_ec_from_logs(tmp_path):
    plant_id = "p1"
    plant_dir = tmp_path / plant_id
    plant_dir.mkdir()

    sensor_log = [
        {"sensor_type": "soil_moisture", "value": 40},
        {"sensor_type": "soil_temperature", "value": 20},
        {"sensor_type": "humidity", "value": 55},
    ]
    (plant_dir / "sensor_reading_log.json").write_text(json.dumps(sensor_log))
    (plant_dir / "irrigation_log.json").write_text(
        json.dumps([{"volume_applied_ml": 100}])
    )
    (plant_dir / "nutrient_application_log.json").write_text(
        json.dumps([{"solution_ec": 1.2}])
    )
    (plant_dir / "runoff_ec_log.json").write_text(json.dumps([{"ec": 1.1}]))

    profile = {"general": {"plant_type": "citrus", "lifecycle_stage": "vegetative"}}
    (tmp_path / f"{plant_id}.json").write_text(json.dumps(profile))
    ec_estimator.train_ec_model(
        [
            {
                "moisture": 40,
                "temperature": 20,
                "irrigation_ml": 100,
                "solution_ec": 1.2,
                "observed_ec": 1.1,
            }
        ],
        plant_id=plant_id,
        base_path=tmp_path,
    )

    est = ec_estimator.estimate_ec(plant_id, base_path=tmp_path)
    assert isinstance(est, float)
