from ..engine.plant_engine import nutrient_efficiency as ne


def test_load_targets_cached(monkeypatch):
    calls = {'count': 0}

    def fake_load_dataset(name):
        calls['count'] += 1
        return {'foo': {'N': 5}}

    monkeypatch.setattr(ne, 'load_dataset', fake_load_dataset)
    ne._load_targets.cache_clear()
    # call twice with same plant_type
    ne.evaluate_nue({'N': 10}, 'foo')
    ne.evaluate_nue({'N': 8}, 'foo')
    assert calls['count'] == 1
