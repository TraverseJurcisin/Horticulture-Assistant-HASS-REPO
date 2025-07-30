import json
from pathlib import Path

import scripts.upload_profile_cache as upc


def test_list_cached_profiles(tmp_path: Path):
    cache_dir = tmp_path / "profile_cache"
    cache_dir.mkdir()
    p = cache_dir / "a.json"
    p.write_text("{}")
    files = upc.list_cached_profiles(cache_dir)
    assert files == [p]


def test_upload_cached_profiles(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / "profile_cache"
    cache_dir.mkdir()
    p = cache_dir / "a.json"
    p.write_text("{\"k\":1}")

    calls = []

    class FakeResponse:
        pass

    def fake_urlopen(req):
        calls.append((req.full_url, req.data))
        return FakeResponse()

    monkeypatch.setattr(upc.urlreq, "urlopen", fake_urlopen)

    upc.upload_cached_profiles("http://example.com/upload", cache_dir)

    assert calls
    assert calls[0][0] == "http://example.com/upload"
    assert json.loads(calls[0][1].decode()) == {"k": 1}
    assert p.exists()


def test_upload_cached_profiles_delete(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / "profile_cache"
    cache_dir.mkdir()
    p = cache_dir / "a.json"
    p.write_text("{\"k\":2}")

    monkeypatch.setattr(upc.urlreq, "urlopen", lambda req: object())

    upc.upload_cached_profiles("http://example.com/upload", cache_dir, delete=True)

    assert not p.exists()

