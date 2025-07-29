from custom_components.horticulture_assistant.utils.cycle_nutrient_totals import calculate_cycle_totals
from custom_components.horticulture_assistant.utils.nutrient_requirements import get_requirements
from plant_engine import growth_stage
from plant_engine.constants import get_stage_multiplier
import json


def compute_expected(plant_type: str):
    with open('data/stage_nutrient_requirements.json') as f:
        stage_req = json.load(f)
    totals = {}
    for stage in growth_stage.list_growth_stages(plant_type):
        days = growth_stage.get_stage_duration(plant_type, stage)
        reqs = stage_req.get(plant_type, {}).get(stage)
        if reqs is None:
            base = get_requirements(plant_type)
            reqs = {n: get_stage_multiplier(stage) * v for n, v in base.items()}
        for nutrient, val in reqs.items():
            totals[nutrient] = totals.get(nutrient, 0.0) + val * days
    return {n: round(v, 2) for n, v in totals.items()}


def test_calculate_cycle_totals_tomato():
    expected = compute_expected('tomato')
    totals = calculate_cycle_totals('tomato')
    assert totals == expected
