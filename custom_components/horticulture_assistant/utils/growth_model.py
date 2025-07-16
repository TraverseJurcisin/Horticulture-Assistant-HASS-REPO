from dataclasses import dataclass
from typing import Optional, Dict
import datetime
import math
import json

@dataclass
class GrowthParameters:
    base_growth_rate: float
    max_growth: float
    onset_day: int
    decay_rate: float

@dataclass
class GrowthObservation:
    date: str
    plant_id: str
    observed_mass: Optional[float] = None
    observed_canopy: Optional[float] = None

class GrowthModel:
    def __init__(self):
        self.plant_profiles: Dict[str, GrowthParameters] = {}
        self.history: Dict[str, list[GrowthObservation]] = {}

    def register_plant(self, plant_id: str, params: GrowthParameters):
        self.plant_profiles[plant_id] = params
        self.history[plant_id] = []

    def expected_growth(self, plant_id: str, day_after_transplant: int) -> float:
        params = self.plant_profiles.get(plant_id)
        if not params:
            raise ValueError(f"Plant {plant_id} not registered")

        t = max(day_after_transplant - params.onset_day, 0)
        growth = params.max_growth * (1 - math.exp(-params.decay_rate * t))
        return min(growth, params.max_growth)

    def log_observation(self, observation: GrowthObservation):
        self.history.setdefault(observation.plant_id, []).append(observation)

    def get_latest_growth_record(self, plant_id: str) -> Optional[GrowthObservation]:
        obs = self.history.get(plant_id, [])
        return obs[-1] if obs else None

    def export_json(self) -> str:
        return json.dumps({
            plant_id: [o.__dict__ for o in obs_list]
            for plant_id, obs_list in self.history.items()
        }, indent=2)