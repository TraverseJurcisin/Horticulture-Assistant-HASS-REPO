from custom_components.horticulture_assistant.utils import tag_registry


def test_list_tags(tmp_path, monkeypatch):
    file = tmp_path / "tags.json"
    file.write_text('{"a": ["p1"], "b": ["p2", "p3"]}')
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", file)
    tag_registry._load_tags.cache_clear()
    assert tag_registry.list_tags() == ["a", "b"]


def test_get_plants_with_tag(tmp_path, monkeypatch):
    file = tmp_path / "tags.json"
    file.write_text('{"x": ["p1", "p2"]}')
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", file)
    tag_registry._load_tags.cache_clear()
    assert tag_registry.get_plants_with_tag("x") == ["p1", "p2"]
    assert tag_registry.get_plants_with_tag("missing") == []


def test_search_tags(tmp_path, monkeypatch):
    file = tmp_path / "tags.json"
    file.write_text('{"cool": ["p1"], "warm": ["p2"]}')
    monkeypatch.setattr(tag_registry, "_TAGS_FILE", file)
    tag_registry._load_tags.cache_clear()
    result = tag_registry.search_tags("co")
    assert result == {"cool": ["p1"]}
    assert tag_registry.search_tags("") == {}


def test_packaged_tags_loaded_by_default():
    tag_registry._load_tags.cache_clear()
    data = tag_registry._load_tags()
    assert tag_registry._TAGS_FILE.exists()
    assert "acid-loving" in data
    assert "backyard" in data
