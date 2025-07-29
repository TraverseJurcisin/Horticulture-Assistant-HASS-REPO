from custom_components.horticulture_assistant.utils.media_inference import (
    infer_media_type,
    MediaInferenceResult,
)


def test_infer_media_type_basic(tmp_path, monkeypatch):
    # Use a temporary data path to avoid writing to repo
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.media_inference.data_path",
        lambda _hass, *parts: str(tmp_path.joinpath(*parts)),
    )
    result = infer_media_type(0.8, 0.3, 0.3, plant_id="test")
    assert result["media_type"] == "Coco Coir"
    assert 0 <= result["confidence"] <= 1
    # result should be saved to file
    assert (tmp_path / "media_type_estimates.json").exists()


def test_infer_media_type_percent_input(monkeypatch):
    # Bypass file writes
    monkeypatch.setattr(
        "custom_components.horticulture_assistant.utils.media_inference.data_path",
        lambda _hass, *parts: "dummy.json",
    )
    monkeypatch.setattr("os.makedirs", lambda *a, **k: None)
    monkeypatch.setattr("builtins.open", lambda *a, **k: open(os.devnull, "w"))
    result = infer_media_type(80, 30, 30)
    assert isinstance(result, dict)
    assert result["media_type"]

