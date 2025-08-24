"""Stage-specific task recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .utils import list_dataset_entries, load_dataset, normalize_key

DATA_FILE = "stages/stage_tasks.json"

_DATA: dict[str, dict[str, list[str]]] = load_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_stage_tasks",
    "generate_task_schedule",
    "generate_cycle_task_plan",
    "TaskScheduleEntry",
]


@dataclass(slots=True, frozen=True)
class TaskScheduleEntry:
    """Single task schedule record."""

    date: date
    tasks: list[str]

    def as_tuple(self) -> tuple[str, list[str]]:
        return self.date.isoformat(), list(self.tasks)


def list_supported_plants() -> list[str]:
    """Return plant types with task definitions."""

    return list_dataset_entries(_DATA)


def get_stage_tasks(plant_type: str, stage: str) -> list[str]:
    """Return task list for a plant stage."""

    return list(_DATA.get(normalize_key(plant_type), {}).get(normalize_key(stage), []))


def generate_task_schedule(
    plant_type: str,
    stage: str,
    start: date,
    days: int,
    interval: int = 7,
) -> list[TaskScheduleEntry]:
    """Return repeating task schedule for the duration of a stage."""

    if days <= 0:
        raise ValueError("days must be positive")
    if interval <= 0:
        raise ValueError("interval must be positive")

    tasks = get_stage_tasks(plant_type, stage)
    schedule: list[TaskScheduleEntry] = []
    current = start
    while current < start + timedelta(days=days):
        schedule.append(TaskScheduleEntry(current, tasks))
        current += timedelta(days=interval)
    return schedule


def generate_cycle_task_plan(
    plant_type: str, start: date, interval: int = 7
) -> list[TaskScheduleEntry]:
    """Return tasks for the entire growth cycle starting at ``start``.

    Stage durations from :mod:`growth_stage` are used to repeat stage tasks
    every ``interval`` days until the next stage begins.
    """

    from . import growth_stage

    schedule: list[TaskScheduleEntry] = []
    current = start
    for stage in growth_stage.list_growth_stages(plant_type):
        days = growth_stage.get_stage_duration(plant_type, stage)
        if not days or days <= 0:
            continue
        stage_tasks = get_stage_tasks(plant_type, stage)
        offset = 0
        while offset < days:
            schedule.append(TaskScheduleEntry(current + timedelta(days=offset), stage_tasks))
            offset += interval
        current += timedelta(days=days)

    return schedule
