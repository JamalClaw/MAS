from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import AgentState, TaskState


class MetricsCollector:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.agent_decisions: List[Dict[str, Any]] = []
        self.snapshots: List[Dict[str, Any]] = []
        self.collision_events = 0
        self.invalid_moves_prevented = 0
        self.deadlocks_detected = 0
        self.deadlock_resolution_times: List[int] = []
        self._active_deadlocks: Dict[str, int] = {}

    def log_event(self, time_step: int, event_type: str, agent_id=None, related_agents=None, task_id=None, cell=None, details="", resolution="") -> None:
        rec = {
            "time_step": time_step,
            "event_type": event_type,
            "agent_id": agent_id,
            "related_agents": related_agents or [],
            "task_id": task_id,
            "cell": list(cell) if cell is not None else None,
            "details": details,
            "resolution": resolution,
        }
        self.events.append(rec)
        if event_type == "INVALID_MOVE_PREVENTED":
            self.invalid_moves_prevented += 1
        if event_type == "COLLISION_EVENT":
            self.collision_events += 1
        if event_type == "DEADLOCK_DETECTED":
            self.deadlocks_detected += 1
            key = details or str(related_agents)
            self._active_deadlocks[key] = time_step
        if event_type == "DEADLOCK_RESOLVED":
            key = details or str(related_agents)
            start = self._active_deadlocks.pop(key, None)
            if start is not None:
                self.deadlock_resolution_times.append(time_step - start)

    def log_agent_decision(self, time_step: int, agent) -> None:
        self.agent_decisions.append({
            "time_step": time_step,
            "agent_id": agent.agent_id,
            "state": agent.state.name,
            "position": list(agent.position),
            "assigned_task": agent.assigned_task_id,
            "selected_action": agent.selected_action.name if agent.selected_action else None,
            "waiting_time": agent.waiting_time,
            "path_length": len(agent.path),
            "carrying_item": agent.carrying_item,
            "distance_traveled": agent.distance_traveled,
            "replanning_count": agent.replanning_count,
        })

    def snapshot(self, time_step: int, agents, task_pool, grid) -> None:
        completed = task_pool.completed()
        assigned = task_pool.assigned()
        unassigned = task_pool.unassigned()
        active_count = sum(1 for a in agents if a.state not in (AgentState.IDLE, AgentState.WAITING))
        utilization = sum(a.active_time for a in agents) / max(1, len(agents) * max(1, time_step))
        completion_times = [t.completion_time - t.creation_time for t in completed if t.completion_time is not None]
        avg_completion = sum(completion_times) / len(completion_times) if completion_times else 0.0
        congestion_index = self.compute_congestion_index(grid)
        self.snapshots.append({
            "time_step": time_step,
            "pending_tasks": len(unassigned),
            "assigned_tasks": len(assigned),
            "completed_tasks": len(completed),
            "throughput": len(completed) / max(1, time_step),
            "avg_completion_time": avg_completion,
            "collision_rate": self.collision_events / max(1, time_step),
            "invalid_moves_prevented": self.invalid_moves_prevented,
            "utilization": utilization,
            "congestion_index": congestion_index,
            "deadlocks_detected": self.deadlocks_detected,
            "active_agents": active_count,
        })

    def compute_congestion_index(self, grid) -> float:
        if not grid.occupancy:
            return 0.0
        vals = [grid.local_congestion(cell) for cell in grid.occupancy]
        return sum(vals) / len(vals)

    def final_summary(self, agents, task_pool, total_time: int) -> Dict[str, Any]:
        completed = task_pool.completed()
        completion_times = [t.completion_time - t.creation_time for t in completed if t.completion_time is not None]
        actual_distances = []
        for t in completed:
            # Approximate static optimal: pickup/dropoff distance only; true agent-origin cost is agent-dependent.
            actual_distances.append(abs(t.pickup[0]-t.dropoff[0]) + abs(t.pickup[1]-t.dropoff[1]))
        return {
            "total_time": total_time,
            "tasks_created": len(task_pool.tasks),
            "tasks_completed": len(completed),
            "throughput": len(completed) / max(1, total_time),
            "avg_completion_time": sum(completion_times) / len(completion_times) if completion_times else 0.0,
            "collision_rate": self.collision_events / max(1, total_time),
            "collision_events": self.collision_events,
            "invalid_moves_prevented": self.invalid_moves_prevented,
            "deadlocks_detected": self.deadlocks_detected,
            "avg_deadlock_resolution_time": sum(self.deadlock_resolution_times) / len(self.deadlock_resolution_times) if self.deadlock_resolution_times else 0.0,
            "agent_utilization": sum(a.active_time for a in agents) / max(1, len(agents) * total_time),
            "agent_metrics": [a.metrics_summary() for a in agents],
        }

    def export(self, out_dir: str | Path, agents, task_pool, total_time: int) -> None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        self._write_json(out / "events.json", self.events)
        self._write_json(out / "agent_decisions.json", self.agent_decisions)
        self._write_json(out / "snapshots.json", self.snapshots)
        self._write_json(out / "summary.json", self.final_summary(agents, task_pool, total_time))
        self._write_csv(out / "events.csv", self.events)
        self._write_csv(out / "snapshots.csv", self.snapshots)

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _write_csv(self, path: Path, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
