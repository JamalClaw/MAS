from __future__ import annotations

import random
from typing import Dict, Iterable, List, Optional

from .models import Cell, Task, TaskState


class TaskPool:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self._counter = 0

    def create_task(self, pickup: Cell, dropoff: Cell, time_step: int) -> Task:
        self._counter += 1
        task = Task(task_id=f"T{self._counter}", pickup=pickup, dropoff=dropoff, creation_time=time_step)
        self.tasks[task.task_id] = task
        return task

    def maybe_generate(self, rng: random.Random, pickups: List[Cell], dropoffs: List[Cell], rate: float, time_step: int) -> Optional[Task]:
        if rng.random() < rate and pickups and dropoffs:
            pickup = rng.choice(pickups)
            dropoff = rng.choice([d for d in dropoffs if d != pickup] or dropoffs)
            return self.create_task(pickup, dropoff, time_step)
        return None

    def unassigned(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.state == TaskState.UNASSIGNED]

    def assigned(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.state == TaskState.ASSIGNED]

    def completed(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.state == TaskState.COMPLETED]

    def assign_task(self, task_id: str, agent_id: int) -> bool:
        task = self.tasks.get(task_id)
        if task is None or task.state != TaskState.UNASSIGNED:
            return False
        task.state = TaskState.ASSIGNED
        task.assigned_agent_id = agent_id
        return True

    def mark_picked_up(self, task_id: str, time_step: int) -> None:
        if task_id in self.tasks:
            self.tasks[task_id].pickup_time = time_step

    def mark_completed(self, task_id: str, time_step: int) -> None:
        task = self.tasks[task_id]
        task.state = TaskState.COMPLETED
        task.completion_time = time_step

    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
