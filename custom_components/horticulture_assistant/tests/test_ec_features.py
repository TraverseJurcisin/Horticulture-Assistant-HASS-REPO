from ..utils.ec_estimator import ECFeatures


def test_asdict_filters_none():
    features = ECFeatures(
        moisture=30,
        temperature=20,
        irrigation_ml=100,
        solution_ec=1.5,
        ambient_temp=None,
        humidity=50,
    )
    data = features.asdict()
    assert data["moisture"] == 30
    assert "ambient_temp" not in data
    assert data["humidity"] == 50
