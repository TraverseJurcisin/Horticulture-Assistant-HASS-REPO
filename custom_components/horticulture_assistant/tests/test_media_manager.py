import plant_engine.media_manager as media


def test_list_supported_media():
    media_types = media.list_supported_media()
    assert "coco" in media_types


def test_get_media_properties():
    props = media.get_media_properties("coco")
    assert props["ph_min"] == 5.5
    assert props["aeration_pct"] == 25
