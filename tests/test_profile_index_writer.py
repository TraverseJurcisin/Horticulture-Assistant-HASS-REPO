import json
import logging

from custom_components.horticulture_assistant.utils.profile_index_writer import generate_profile_index


def test_generate_profile_index_logging(tmp_path, caplog) -> None:
    plant_dir = tmp_path / "alpha"
    plant_dir.mkdir()

    sample = plant_dir / "general.json"
    sample.write_text(json.dumps({"example": True}), encoding="utf-8")

    caplog.set_level(logging.INFO)
    result = generate_profile_index("alpha", base_path=str(tmp_path), overwrite=True)

    assert result == "alpha"
    created_messages = [rec.message for rec in caplog.records if "Created file" in rec.message]
    assert created_messages, "Expected creation log when index did not previously exist"
    assert not any("Overwrote existing file" in rec.message for rec in caplog.records)

    caplog.clear()
    sample.write_text(json.dumps({"example": False}), encoding="utf-8")

    generate_profile_index("alpha", base_path=str(tmp_path), overwrite=True)

    assert any("Overwrote existing file" in rec.message for rec in caplog.records)
