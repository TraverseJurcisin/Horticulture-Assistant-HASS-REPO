import json
import pathlib


def _collect_paths(data, prefix=()):
    paths = set()
    if isinstance(data, dict):
        for key, val in data.items():
            paths |= _collect_paths(val, prefix + (key,))
    else:
        paths.add(prefix)
    return paths


def test_translations_cover_strings():
    base = pathlib.Path(__file__).parents[1] / "custom_components" / "horticulture_assistant"
    strings = json.loads((base / "strings.json").read_text(encoding="utf-8"))
    en = json.loads((base / "translations" / "en.json").read_text(encoding="utf-8"))

    string_paths = _collect_paths(strings)
    en_paths = _collect_paths(en)
    missing = string_paths - en_paths
    assert not missing, f"Missing translations for: {sorted('.'.join(p) for p in missing)}"

    extra = en_paths - string_paths
    assert not extra, f"Unknown translations for: {sorted('.'.join(p) for p in extra)}"


def _collect_values(data):
    values: list[str] = []
    if isinstance(data, dict):
        for val in data.values():
            values.extend(_collect_values(val))
    else:
        values.append(data)
    return values


def test_translation_values_non_empty():
    base = pathlib.Path(__file__).parents[1] / "custom_components" / "horticulture_assistant"
    en = json.loads((base / "translations" / "en.json").read_text(encoding="utf-8"))
    for val in _collect_values(en):
        assert isinstance(val, str) and val, "Empty translation value detected"
