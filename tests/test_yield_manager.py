from plant_engine import yield_manager


def test_record_and_total_yield(tmp_path):
    plant_id = 'testplant'
    yield_manager.YIELD_DIR = str(tmp_path)

    yield_manager.record_harvest(plant_id, grams=100, fruit_count=3, date='2025-01-01')
    yield_manager.record_harvest(plant_id, grams=80, fruit_count=2, date='2025-01-10')

    history = yield_manager.load_yield_history(plant_id)
    assert len(history) == 2
    assert history[0].yield_grams == 100

    total = yield_manager.get_total_yield(plant_id)
    assert total == 180


def test_get_total_nutrient_removal(tmp_path):
    plant_id = 'removalplant'
    yield_manager.YIELD_DIR = str(tmp_path)

    yield_manager.record_harvest(plant_id, grams=1000, date='2025-01-01')

    removal = yield_manager.get_total_nutrient_removal(plant_id, 'lettuce')
    data = removal.as_dict()['nutrients_g']

    assert data['N'] == 1.2
    assert data['P'] == 0.2
    assert data['K'] == 1.5
