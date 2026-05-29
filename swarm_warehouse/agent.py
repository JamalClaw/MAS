from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .models import ActionType, AgentState, Bid, Cell, MovementIntent, SimulationConfig, Task, TaskState


class RobotAgent:
    def __init__(self, agent_id: int, start_position: Cell):
        self.agent_id = agent_id
        self.position = start_position
        self.state = AgentState.IDLE
        self.assigned_task_id: Optional[str] = None
        self.carrying_item = False
        self.path: List[Cell] = []
        self.path_index = 0
        # waiting_time is the current consecutive waiting streak.
        # total_waiting_time is the accumulated number of simulation steps spent waiting.
        self.waiting_time = 0
        self.total_waiting_time = 0
        self.waiting_for_agent_id: Optional[int] = None
        self.needs_replan = False
        self.selected_action: ActionType = ActionType.NONE
        self.next_cell: Cell = start_position
        self.active_time = 0
        self.idle_time = 0
        self.distance_traveled = 0
        self.replanning_count = 0
        self.tasks_completed = 0
        self.conflicts_involved = 0
        self.deadlocks_involved = 0
        self.bid_values: List[float] = []

    def can_bid(self) -> bool:
        return self.assigned_task_id is None and self.state in (AgentState.IDLE, AgentState.BIDDING, AgentState.WAITING)

    def assign_task(self, task_id: str) -> None:
        self.assigned_task_id = task_id
        self.state = AgentState.ASSIGNED
        self.carrying_item = False
        self.path = []
        self.path_index = 0
        self.needs_replan = True

    def compute_bid(self, task: Task, planner, reservation_table, current_time: int, config: SimulationConfig) -> Optional[Bid]:
        if not self.can_bid():
            return None
        p1 = planner.a_star(self.position, task.pickup)
        p2 = planner.a_star(task.pickup, task.dropoff)
        if p1 is None or p2 is None:
            return None
        distance = float(max(0, len(p1) - 1) + max(0, len(p2) - 1))
        congestion = sum(planner.grid.local_congestion(c) for c in p1[:15]) / max(1, min(len(p1), 15))
        workload = 0.0 if self.assigned_task_id is None else 1.0
        reservation_delay = float(reservation_table.reservation_delay_estimate(p1, current_time, self.agent_id))
        value = (
            config.alpha_distance * distance
            + config.beta_congestion * congestion
            + config.gamma_workload * workload
            + config.delta_reservation * reservation_delay
        )
        self.bid_values.append(value)
        return Bid(self.agent_id, task.task_id, value, {
            "distance": distance,
            "congestion": round(congestion, 3),
            "workload": workload,
            "reservation_delay": reservation_delay,
        })

    def target_cell(self, task_pool) -> Optional[Cell]:
        if self.assigned_task_id is None:
            return None
        task = task_pool.get(self.assigned_task_id)
        if task is None or task.state == TaskState.COMPLETED:
            return None
        return task.dropoff if self.carrying_item else task.pickup

    def plan_or_replan(self, planner, reservation_table, task_pool, current_time: int, config: SimulationConfig, metrics) -> None:
        target = self.target_cell(task_pool)
        if target is None:
            return
        if self.path and not self.needs_replan and self.path_index < len(self.path):
            return
        self.state = AgentState.REPLANNING if self.needs_replan else self.state
        reservation_table.release_agent_future(self.agent_id, current_time)
        path = planner.cooperative_a_star(
            self.position,
            target,
            current_time,
            reservation_table,
            self.agent_id,
            max_time_expansion=max(80, config.grid_rows * config.grid_cols // 2),
        )
        if path is None:
            path = planner.a_star(self.position, target)
            metrics.log_event(current_time, "PATH_REPLANNED", self.agent_id, task_id=self.assigned_task_id, details="fallback A* used")
        else:
            metrics.log_event(current_time, "PATH_PLANNED" if not self.needs_replan else "PATH_REPLANNED", self.agent_id, task_id=self.assigned_task_id, details="Cooperative A* path reserved")
        if path:
            self.path = path
            self.path_index = 0
            reservation_table.reserve_path(self.agent_id, path, current_time, config.reservation_horizon)
            self.needs_replan = False
            self.replanning_count += 1
            if self.carrying_item:
                self.state = AgentState.MOVING_TO_DROPOFF
            else:
                self.state = AgentState.MOVING_TO_PICKUP
        else:
            self.selected_action = ActionType.WAIT
            self.next_cell = self.position
            self.waiting_time += 1


    def plan_or_replan_naive(self, planner, task_pool, current_time: int, metrics) -> None:
        """Plan using ordinary A* only, without cooperative reservations.

        This is used by the naive baseline strategy. It intentionally ignores
        future space-time reservations, congestion, edge-swap prevention, and
        deadlock recovery so it can serve as a simple baseline controller.
        """
        target = self.target_cell(task_pool)
        if target is None:
            return
        if self.path and not self.needs_replan and self.path_index < len(self.path):
            return
        self.state = AgentState.REPLANNING if self.needs_replan else self.state
        path = planner.a_star(self.position, target)
        if path:
            self.path = path
            self.path_index = 0
            self.needs_replan = False
            self.replanning_count += 1
            if self.carrying_item:
                self.state = AgentState.MOVING_TO_DROPOFF
            else:
                self.state = AgentState.MOVING_TO_PICKUP
            metrics.log_event(current_time, "NAIVE_PATH_PLANNED", self.agent_id, task_id=self.assigned_task_id, details="standard A* path planned")
        else:
            self.selected_action = ActionType.WAIT
            self.next_cell = self.position
            self.waiting_time += 1
            metrics.log_event(current_time, "NAIVE_PATH_FAILED", self.agent_id, task_id=self.assigned_task_id, details="standard A* failed")

    def prepare_intent(self, task_pool, current_time: int) -> MovementIntent:
        self.selected_action = ActionType.WAIT
        self.next_cell = self.position
        if self.assigned_task_id is None:
            self.state = AgentState.IDLE
            return MovementIntent(self.agent_id, self.position, self.position, ActionType.WAIT)
        task = task_pool.get(self.assigned_task_id)
        if task is None:
            return MovementIntent(self.agent_id, self.position, self.position, ActionType.WAIT)
        if not self.carrying_item and self.position == task.pickup:
            self.selected_action = ActionType.PICKUP
            self.next_cell = self.position
            return MovementIntent(self.agent_id, self.position, self.position, ActionType.PICKUP)
        if self.carrying_item and self.position == task.dropoff:
            self.selected_action = ActionType.DELIVER
            self.next_cell = self.position
            return MovementIntent(self.agent_id, self.position, self.position, ActionType.DELIVER)
        if self.path and self.path_index + 1 < len(self.path):
            self.next_cell = self.path[self.path_index + 1]
            if self.next_cell != self.position:
                self.selected_action = ActionType.MOVE
            else:
                self.selected_action = ActionType.WAIT
        else:
            self.selected_action = ActionType.WAIT
            self.needs_replan = True
        return MovementIntent(self.agent_id, self.position, self.next_cell, self.selected_action)

    def force_wait(self, blocker_id: Optional[int] = None) -> None:
        self.selected_action = ActionType.WAIT
        self.next_cell = self.position
        # Do not increment waiting_time here. Waiting is counted exactly once
        # during execute(). Otherwise a forced wait is counted twice in the same tick.
        self.waiting_for_agent_id = blocker_id
        self.state = AgentState.WAITING

    def execute(self, task_pool, time_step: int, metrics) -> None:
        had_task = self.assigned_task_id is not None
        action = self.selected_action

        if action == ActionType.MOVE:
            old = self.position
            self.position = self.next_cell
            self.distance_traveled += 1
            self.waiting_time = 0
            self.waiting_for_agent_id = None
            if self.path_index + 1 < len(self.path):
                self.path_index += 1
            metrics.log_event(time_step, "AGENT_MOVED", self.agent_id, task_id=self.assigned_task_id, cell=self.position, details=f"{old}->{self.position}")

        elif action == ActionType.PICKUP:
            task_pool.mark_picked_up(self.assigned_task_id, time_step)
            self.carrying_item = True
            self.needs_replan = True
            self.path = []
            self.path_index = 0
            self.waiting_time = 0
            self.waiting_for_agent_id = None
            self.state = AgentState.MOVING_TO_DROPOFF
            metrics.log_event(time_step, "TASK_PICKED_UP", self.agent_id, task_id=self.assigned_task_id, cell=self.position)

        elif action == ActionType.DELIVER:
            completed_task_id = self.assigned_task_id
            task_pool.mark_completed(completed_task_id, time_step)
            metrics.log_event(time_step, "TASK_COMPLETED", self.agent_id, task_id=completed_task_id, cell=self.position)
            self.tasks_completed += 1
            self.assigned_task_id = None
            self.carrying_item = False
            self.path = []
            self.path_index = 0
            self.state = AgentState.IDLE
            self.waiting_time = 0
            self.waiting_for_agent_id = None

        elif action == ActionType.WAIT:
            if had_task:
                self.waiting_time += 1
                self.total_waiting_time += 1
            else:
                # Idle waiting is not a conflict/deadlock wait.
                self.waiting_time = 0
                self.waiting_for_agent_id = None
            metrics.log_event(time_step, "AGENT_WAITED", self.agent_id, task_id=self.assigned_task_id, cell=self.position)

        # Count exactly one time category per tick. This avoids impossible summaries
        # where active_time + idle_time + waiting_time exceeds total simulation time.
        if action == ActionType.WAIT:
            if not had_task:
                self.idle_time += 1
        elif had_task:
            self.active_time += 1
        else:
            self.idle_time += 1

    def progress_score(self) -> float:
        if not self.path:
            return 0.0
        return self.path_index / max(1, len(self.path) - 1)

    def metrics_summary(self):
        return {
            "agent_id": self.agent_id,
            "tasks_completed_by_agent": self.tasks_completed,
            "active_time": self.active_time,
            "idle_time": self.idle_time,
            "waiting_time": self.total_waiting_time,
            "current_wait_streak": self.waiting_time,
            "replanning_count": self.replanning_count,
            "distance_traveled": self.distance_traveled,
            "conflicts_involved": self.conflicts_involved,
            "deadlocks_involved": self.deadlocks_involved,
            "average_bid_value": sum(self.bid_values) / len(self.bid_values) if self.bid_values else 0.0,
        }
