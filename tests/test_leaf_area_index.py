from plant_engine.leaf_area_index import (
    get_leaf_area_index,
    estimate_leaf_area_index,
)


def test_get_leaf_area_index():
    assert get_leaf_area_index("tomato", "vegetative") == 3.0


def test_estimate_leaf_area_index_dataset():
    assert estimate_leaf_area_index("tomato", "vegetative") == 3.0


def test_estimate_leaf_area_index_fallback(monkeypatch):
    from plant_engine import leaf_area_index as lai

    monkeypatch.setattr(lai, "estimate_canopy_area", lambda p, s=None: 0.2)
    assert estimate_leaf_area_index("unknown") == round(0.2 * 3, 2)
