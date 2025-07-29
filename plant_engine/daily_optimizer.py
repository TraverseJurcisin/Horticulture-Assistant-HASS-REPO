from __future__ import annotations

"""Generate consolidated daily management plans.

This helper pulls together recommendations from the environment,
fertigation and pest management modules so applications have a
single entry point for actionable tasks.
"""

from dataclasses import dataclass
from typing import Iterable, Mapping, Dict, Any

from . import environment_manager as env
from . import fertigation
from . import pest_manager


@dataclass(slots=True)
class DailyPlan:
    """Summary of recommended daily actions."""

    environment_actions: Dict[str, str]
    fertigation_schedule: Dict[str, float]
    cost_total: float
    cost_breakdown: Dict[str, float]
    pest_plan: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "environment_actions": self.environment_actions,
            "fertigation_schedule": self.fertigation_schedule,
            "cost_total": self.cost_total,
            "cost_breakdown": self.cost_breakdown,
            "pest_plan": self.pest_plan,
        }


def build_daily_plan(
    plant_type: str,
    stage: str,
    *,
    temp_c: float | None = None,
    humidity_pct: float | None = None,
    wind_m_s: float | None = None,
    pests: Iterable[str] | None = None,
    water_profile: Mapping[str, float] | None = None,
    include_micro: bool = False,
    fertilizers: Mapping[str, str] | None = None,
    volume_l: float = 1.0,
) -> DailyPlan:
    """Return a :class:`DailyPlan` for the given crop conditions."""

    env_actions: Dict[str, str] = {}

    t_act = env.recommend_temperature_action(temp_c, humidity_pct, plant_type)
    if t_act:
        env_actions["temperature"] = t_act

    h_act = env.recommend_humidity_action(humidity_pct, plant_type)
    if h_act:
        env_actions["humidity"] = h_act

    w_act = env.recommend_wind_action(wind_m_s, plant_type)
    if w_act:
        env_actions["wind"] = w_act

    sched, total, breakdown, _warn, _diag = fertigation.recommend_precise_fertigation(
        plant_type,
        stage,
        volume_l,
        water_profile,
        include_micro=include_micro,
        fertilizers=fertilizers,
    )

    pest_plan = (
        pest_manager.build_pest_management_plan(plant_type, pests)
        if pests
        else {}
    )

    return DailyPlan(env_actions, sched, total, breakdown, pest_plan)


__all__ = ["DailyPlan", "build_daily_plan"]
