import tempfile
import os
from plant_engine.water_deficit_tracker import update_water_balance


def test_update_water_balance_tmpdir():
    with tempfile.TemporaryDirectory() as tmp:
        result = update_water_balance("test", 1000, 500, storage_path=tmp)
        assert result["ml_available"] == 500
        assert os.path.exists(os.path.join(tmp, "test.json"))
