import tempfile
import os
from plant_engine.water_deficit_tracker import update_water_balance


def test_update_water_balance_tmpdir():
    with tempfile.TemporaryDirectory() as tmp:
        result = update_water_balance("test", 1000, 500, storage_path=tmp)
        assert result["ml_available"] == 500
        assert os.path.exists(os.path.join(tmp, "test.json"))


def test_update_water_balance_with_rootzone():
    with tempfile.TemporaryDirectory() as tmp:
        result = update_water_balance(
            "test",
            1000,
            200,
            storage_path=tmp,
            rootzone_ml=1200,
            mad_pct=0.4,
        )
        assert result["taw_ml"] == 1200
        assert result["mad_pct"] == 0.4
