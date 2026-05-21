from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import ActionType, Conflict, ConflictType, MovementIntent, SimulationConfig


class ConflictResolver:
    def __init__(self, config: SimulationConfig):
        self.config = config

    def detect(self, intents: List[MovementIntent]) -> List[Conflict]:
        conflicts: List[Conflict] = []
        by_agent = {i.agent_id: i for i in intents}
        for idx in range(len(intents)):
            a = intents[idx]
            for jdx in range(idx + 1, len(intents)):
                b = intents[jdx]
                if a.next_cell == b.next_cell and a.action == ActionType.MOVE and b.action == ActionType.MOVE:
                    conflicts.append(Conflict(ConflictType.VERTEX_CONFLICT, (a.agent_id, b.agent_id), a.next_cell, "same target cell"))
                if a.current_cell == b.next_cell and a.next_cell == b.current_cell and a.action == ActionType.MOVE and b.action == ActionType.MOVE:
                    conflicts.append(Conflict(ConflictType.EDGE_CONFLICT, (a.agent_id, b.agent_id), a.next_cell, "edge swap"))
                if a.next_cell == b.current_cell and b.action == ActionType.WAIT and a.action == ActionType.MOVE:
                    conflicts.append(Conflict(ConflictType.BLOCKING_CONFLICT, (a.agent_id, b.agent_id), b.current_cell, "moving into waiting occupied cell"))
                if b.next_cell == a.current_cell and a.action == ActionType.WAIT and b.action == ActionType.MOVE:
                    conflicts.append(Conflict(ConflictType.BLOCKING_CONFLICT, (b.agent_id, a.agent_id), a.current_cell, "moving into waiting occupied cell"))
        return conflicts

    def priority(self, agent) -> float:
        progress = agent.progress_score()
        return (
            self.config.priority_carrying_weight * (1.0 if agent.carrying_item else 0.0)
            + self.config.priority_waiting_weight * agent.waiting_time
            + self.config.priority_progress_weight * progress
            - self.config.priority_id_weight * agent.agent_id
        )

    def resolve(self, conflicts: List[Conflict], agents_by_id: Dict[int, object], metrics, time_step: int) -> Set[int]:
        forced_wait: Set[int] = set()
        for conflict in conflicts:
            participants = [agents_by_id[aid] for aid in conflict.involved_agents]
            winner = max(participants, key=lambda a: (self.priority(a), -a.agent_id))
            losers = [a for a in participants if a.agent_id != winner.agent_id]
            for loser in losers:
                forced_wait.add(loser.agent_id)
                loser.waiting_for_agent_id = winner.agent_id
            metrics.log_event(
                time_step,
                "CONFLICT_RESOLVED",
                winner.agent_id,
                related_agents=[a.agent_id for a in losers],
                cell=conflict.cell,
                details=f"{conflict.conflict_type.name}: {conflict.description}",
                resolution=f"A{winner.agent_id} keeps movement; losers wait {[a.agent_id for a in losers]}",
            )
        return forced_wait
