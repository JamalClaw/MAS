from __future__ import annotations

from typing import Dict, List, Set, Tuple


class DeadlockDetector:
    """Wait-for-graph deadlock detector with persistence filtering.

    A one-tick wait cycle is usually just a transient movement conflict, not a real
    deadlock. The detector therefore reports a deadlock only when the same cycle is
    observed for several consecutive ticks, or when every participant has already
    waited beyond the configured threshold.
    """

    def __init__(self) -> None:
        self._candidate_counts: Dict[Tuple[int, ...], int] = {}
        self._active_cycles: Set[Tuple[int, ...]] = set()

    def build_wait_for_graph(self, agents) -> Dict[int, int]:
        graph = {}
        for a in agents:
            if a.waiting_for_agent_id is not None and a.waiting_for_agent_id != a.agent_id:
                graph[a.agent_id] = a.waiting_for_agent_id
        return graph

    def detect_cycle(self, graph: Dict[int, int]) -> List[int]:
        visited: Set[int] = set()
        for start in list(graph):
            if start in visited:
                continue
            path: List[int] = []
            index: Dict[int, int] = {}
            node = start
            while node in graph:
                if node in index:
                    return path[index[node]:]
                if node in visited:
                    break
                index[node] = len(path)
                path.append(node)
                visited.add(node)
                node = graph[node]
        return []

    @staticmethod
    def _signature(cycle: List[int]) -> Tuple[int, ...]:
        """Canonical cycle signature independent of starting node."""
        if not cycle:
            return tuple()
        rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(len(cycle))]
        return min(rotations)

    def detect(self, agents, min_wait_streak: int = 2, min_persistence: int = 2) -> List[int]:
        graph = self.build_wait_for_graph(agents)
        cycle = self.detect_cycle(graph)
        if not cycle:
            self._candidate_counts.clear()
            return []

        sig = self._signature(cycle)
        self._candidate_counts[sig] = self._candidate_counts.get(sig, 0) + 1

        by_id = {a.agent_id: a for a in agents}
        all_waited_long_enough = all(by_id[aid].waiting_time >= min_wait_streak for aid in sig)
        persisted_long_enough = self._candidate_counts[sig] >= min_persistence

        # Do not repeatedly report the exact same active deadlock every tick.
        if sig in self._active_cycles:
            return []

        # A real deadlock must be both persistent and composed of agents that have
        # actually been waiting for several consecutive ticks. Otherwise normal
        # one-step conflict avoidance gets mislabeled as a deadlock.
        if all_waited_long_enough and persisted_long_enough:
            self._active_cycles.add(sig)
            return list(sig)
        return []

    def mark_resolved(self, cycle: List[int]) -> None:
        sig = self._signature(cycle)
        self._active_cycles.discard(sig)
        self._candidate_counts.pop(sig, None)

    def resolve(self, cycle: List[int], agents_by_id, reservation_table, conflict_resolver, time_step: int, metrics) -> None:
        if not cycle:
            return
        participants = [agents_by_id[aid] for aid in cycle]
        winner = max(participants, key=lambda a: (conflict_resolver.priority(a), -a.agent_id))
        signature = "->".join(f"A{x}" for x in cycle + [cycle[0]])
        metrics.log_event(time_step, "DEADLOCK_DETECTED", winner.agent_id, related_agents=cycle, details=signature)

        for a in participants:
            a.state = a.state.DEADLOCK_RECOVERY
            if a.agent_id != winner.agent_id:
                reservation_table.release_agent_future(a.agent_id, time_step)
                a.needs_replan = True
                a.waiting_for_agent_id = None

        # In this simulator, recovery is deterministic and immediate: lower-priority
        # participants release reservations and replan in the next tick. The event is
        # still logged explicitly to support scenario validation.
        metrics.log_event(
            time_step + 1,
            "DEADLOCK_RESOLVED",
            winner.agent_id,
            related_agents=cycle,
            details=signature,
            resolution=f"A{winner.agent_id} kept priority; lower-priority agents released reservations and replanned",
        )
        self.mark_resolved(cycle)
