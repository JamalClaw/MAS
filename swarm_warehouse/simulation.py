from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from .agent import RobotAgent
from .auction import AuctionProtocol
from .conflict import ConflictResolver
from .deadlock import DeadlockDetector
from .grid import WarehouseGrid, default_layout
from .message_bus import MessageBus
from .metrics import MetricsCollector
from .models import ActionType, AgentState, Cell, SimulationConfig
from .path_planner import PathPlanner
from .reservation import ReservationTable
from .task_pool import TaskPool


class WarehouseSimulation:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config.random_seed)
        self.time_step = 0
        self.reset_requested = False
        obstacles, pickups, dropoffs = self._layout_for_scenario(config.scenario)
        self.grid = WarehouseGrid(config.grid_rows, config.grid_cols, obstacles, pickups, dropoffs)
        self.task_pool = TaskPool()
        self.reservations = ReservationTable()
        self.message_bus = MessageBus()
        self.metrics = MetricsCollector()
        self.planner = PathPlanner(self.grid)
        self.auction = AuctionProtocol(config)
        self.conflict_resolver = ConflictResolver(config)
        self.deadlock_detector = DeadlockDetector()
        self.agents = self._spawn_agents(config.num_agents)
        self.grid.set_agent_positions({a.agent_id: a.position for a in self.agents})

    def reset(self) -> None:
        """Reset the simulation to its initial deterministic state.

        This is used by the Pygame dashboard Reset control. It rebuilds the
        grid, agents, task pool, reservations, logs, metrics, and RNG from the
        current SimulationConfig. The same seed is reused, so reset gives a
        reproducible fresh run instead of merely clearing the screen.
        """
        config = self.config
        self.__init__(config)

    def _layout_for_scenario(self, scenario: str):
        obstacles, pickups, dropoffs = default_layout(self.config.grid_rows, self.config.grid_cols)
        if scenario == "deadlock":
            # Narrow single corridor to provoke wait cycles and conflict handling.
            obstacles = set()
            mid = self.config.grid_rows // 2
            for r in range(self.config.grid_rows):
                for c in range(self.config.grid_cols):
                    if r not in (mid, mid - 1, mid + 1) and c not in (2, self.config.grid_cols - 3):
                        obstacles.add((r, c))
            pickups = [(mid, 1), (mid, self.config.grid_cols - 2)]
            dropoffs = [(mid, self.config.grid_cols - 2), (mid, 1)]
            obstacles -= set(pickups) | set(dropoffs)
        return obstacles, pickups, dropoffs

    def _spawn_agents(self, n: int) -> List[RobotAgent]:
        free = self.grid.all_free_cells()
        # Prefer corners and open border cells, deterministic shuffle after seed.
        preferred = []
        for cell in free:
            r, c = cell
            if r in (0, 1, self.config.grid_rows - 2, self.config.grid_rows - 1) or c in (0, 1, self.config.grid_cols - 2, self.config.grid_cols - 1):
                if cell not in self.grid.pickups and cell not in self.grid.dropoffs:
                    preferred.append(cell)
        self.rng.shuffle(preferred)
        starts = preferred[:n]
        if len(starts) < n:
            rest = [c for c in free if c not in starts and c not in self.grid.pickups and c not in self.grid.dropoffs]
            self.rng.shuffle(rest)
            starts.extend(rest[: n - len(starts)])
        return [RobotAgent(i + 1, starts[i]) for i in range(n)]

    @property
    def agents_by_id(self) -> Dict[int, RobotAgent]:
        return {a.agent_id: a for a in self.agents}

    def step(self) -> None:
        self.time_step += 1
        t = self.time_step
        self.reservations.clear_expired(t)

        # Dynamic task generation.
        new_task = self.task_pool.maybe_generate(self.rng, self.grid.pickups, self.grid.dropoffs, self.config.task_generation_rate, t)
        if new_task:
            self.metrics.log_event(t, "TASK_CREATED", task_id=new_task.task_id, details=f"{new_task.pickup}->{new_task.dropoff}")

        # Deterministic decentralized auction protocol phase.
        self.auction.run(self.agents, self.task_pool, self.planner, self.reservations, t, self.metrics)

        # Plan or replan paths.
        for agent in self.agents:
            if agent.assigned_task_id is not None:
                agent.plan_or_replan(self.planner, self.reservations, self.task_pool, t, self.config, self.metrics)

        # Prepare movement intents.
        intents = [a.prepare_intent(self.task_pool, t) for a in self.agents]

        # Basic validity/occupancy prevention before pairwise conflicts.
        occupied = {a.position: a.agent_id for a in self.agents}
        forced_wait: Dict[int, Optional[int]] = {}
        for intent in intents:
            agent = self.agents_by_id[intent.agent_id]
            if intent.action == ActionType.MOVE:
                if not self.grid.valid_move_target(intent.next_cell):
                    forced_wait[agent.agent_id] = None
                    self.metrics.log_event(t, "INVALID_MOVE_PREVENTED", agent.agent_id, cell=intent.next_cell, details="outside grid or obstacle")
                elif intent.next_cell in occupied and occupied[intent.next_cell] != agent.agent_id:
                    other = occupied[intent.next_cell]
                    # If other is not moving away, block now; if it is moving away, pairwise edge/vertex resolver handles.
                    other_intent = next((x for x in intents if x.agent_id == other), None)
                    if other_intent is None or other_intent.next_cell == intent.next_cell:
                        forced_wait[agent.agent_id] = other
                        self.metrics.log_event(t, "INVALID_MOVE_PREVENTED", agent.agent_id, related_agents=[other], cell=intent.next_cell, details="occupied target")

        # Pairwise conflict resolution.
        conflicts = self.conflict_resolver.detect(intents)
        for c in conflicts:
            for aid in c.involved_agents:
                self.agents_by_id[aid].conflicts_involved += 1
            self.metrics.log_event(t, "CONFLICT_DETECTED", related_agents=list(c.involved_agents), cell=c.cell, details=c.conflict_type.name)
        pairwise_wait = self.conflict_resolver.resolve(conflicts, self.agents_by_id, self.metrics, t)
        for aid in pairwise_wait:
            # Waiting-for winner is set in resolver when applicable.
            forced_wait.setdefault(aid, self.agents_by_id[aid].waiting_for_agent_id)

        # Apply forced waits and replanning trigger.
        for aid, blocker in forced_wait.items():
            a = self.agents_by_id[aid]
            a.force_wait(blocker)
            if a.waiting_time > self.config.wait_threshold:
                a.needs_replan = True

        # Final safety gate. Conflict resolution can create secondary blocking cases
        # (for example, A was allowed to enter B's cell, then B was forced to wait).
        # This loop converts any remaining unsafe move into WAIT before execution.
        for _ in range(len(self.agents) + 1):
            changed = False
            current_pos = {a.position: a.agent_id for a in self.agents}
            moving = {a.agent_id: a for a in self.agents if a.selected_action == ActionType.MOVE}

            # Duplicate target cells: keep highest priority, force others to wait.
            targets = {}
            for a in moving.values():
                targets.setdefault(a.next_cell, []).append(a)
            for cell, contenders in targets.items():
                if len(contenders) > 1:
                    winner = max(contenders, key=lambda ag: (self.conflict_resolver.priority(ag), -ag.agent_id))
                    for loser in contenders:
                        if loser.agent_id != winner.agent_id:
                            loser.force_wait(winner.agent_id)
                            self.metrics.log_event(t, "INVALID_MOVE_PREVENTED", loser.agent_id, related_agents=[winner.agent_id], cell=cell, details="final safety duplicate target")
                            changed = True

            # Moving into a currently occupied cell is legal only if the occupant is moving away
            # and not swapping back into the mover's current cell.
            for a in list(moving.values()):
                occupant = current_pos.get(a.next_cell)
                if occupant is not None and occupant != a.agent_id:
                    other = self.agents_by_id[occupant]
                    if other.selected_action != ActionType.MOVE or other.next_cell == a.position:
                        a.force_wait(occupant)
                        self.metrics.log_event(t, "INVALID_MOVE_PREVENTED", a.agent_id, related_agents=[occupant], cell=a.next_cell, details="final safety occupied target")
                        changed = True
            if not changed:
                break

        # Deadlock detection and deterministic recovery.
        cycle = self.deadlock_detector.detect(
            self.agents,
            min_wait_streak=max(2, self.config.wait_threshold),
            min_persistence=max(2, self.config.wait_threshold),
        )
        if cycle:
            for aid in cycle:
                self.agents_by_id[aid].deadlocks_involved += 1
            self.deadlock_detector.resolve(cycle, self.agents_by_id, self.reservations, self.conflict_resolver, t, self.metrics)

        # Execute synchronously.
        old_positions = {a.agent_id: a.position for a in self.agents}
        for agent in self.agents:
            if agent.waiting_time > self.config.wait_threshold and agent.assigned_task_id is not None:
                agent.needs_replan = True
            agent.execute(self.task_pool, t, self.metrics)
            self.metrics.log_agent_decision(t, agent)

        # Validate no actual collision after execution.
        positions = {}
        for agent in self.agents:
            if agent.position in positions:
                self.metrics.collision_events += 1
                self.metrics.log_event(t, "COLLISION_EVENT", agent.agent_id, related_agents=[positions[agent.position]], cell=agent.position, details="post-step collision")
            positions[agent.position] = agent.agent_id
        self.grid.set_agent_positions({a.agent_id: a.position for a in self.agents})
        self.metrics.snapshot(t, self.agents, self.task_pool, self.grid)

    def run(self, output_dir: Optional[str] = None, render: Optional[bool] = None) -> Dict:
        render_enabled = self.config.enable_pygame if render is None else render
        dashboard = None
        if render_enabled:
            from .visualization import VisualizationDashboard
            dashboard = VisualizationDashboard(self)

        while self.time_step < self.config.max_time_steps:
            if dashboard:
                if not dashboard.handle_events():
                    break
                if dashboard.should_advance():
                    self.step()
                dashboard.render()
            else:
                self.step()
        if output_dir:
            self.metrics.export(output_dir, self.agents, self.task_pool, self.time_step)
        return self.metrics.final_summary(self.agents, self.task_pool, self.time_step)


def scenario_config(name: str) -> SimulationConfig:
    base = SimulationConfig(scenario=name)
    if name == "baseline":
        return base
    if name == "high_load":
        base.task_generation_rate = 0.45
        base.num_agents = 8
    elif name == "high_density":
        base.num_agents = 14
        base.task_generation_rate = 0.22
    elif name == "deadlock":
        base.num_agents = 4
        base.task_generation_rate = 0.35
        base.grid_rows = 12
        base.grid_cols = 18
        base.wait_threshold = 3
    elif name == "dynamic":
        base.task_generation_rate = 0.25
        base.num_agents = 8
    elif name == "scalability":
        base.num_agents = 12
        base.task_generation_rate = 0.30
    else:
        raise ValueError(f"Unknown scenario: {name}")
    return base
