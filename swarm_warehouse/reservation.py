from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .models import Cell, Reservation, ReservationType

Edge = Tuple[Cell, Cell, int]


class ReservationTable:
    def __init__(self):
        self.vertex: Dict[Tuple[Cell, int], int] = {}
        self.edge: Dict[Edge, int] = {}

    def reserve_path(self, agent_id: int, path: List[Cell], start_time: int, horizon: Optional[int] = None) -> bool:
        if not path:
            return False
        max_len = len(path) if horizon is None else min(len(path), horizon)
        # Validate first to avoid partial reservations.
        for idx in range(max_len):
            t = start_time + idx
            cell = path[idx]
            owner = self.vertex.get((cell, t))
            if owner is not None and owner != agent_id:
                return False
            if idx > 0:
                prev = path[idx - 1]
                reverse_owner = self.edge.get((cell, prev, t))
                if reverse_owner is not None and reverse_owner != agent_id:
                    return False
        self.release_agent_future(agent_id, start_time)
        for idx in range(max_len):
            t = start_time + idx
            cell = path[idx]
            self.vertex[(cell, t)] = agent_id
            if idx > 0:
                prev = path[idx - 1]
                self.edge[(prev, cell, t)] = agent_id
        return True

    def is_cell_reserved(self, cell: Cell, time_step: int, by_agent: Optional[int] = None) -> bool:
        owner = self.vertex.get((cell, time_step))
        return owner is not None and owner != by_agent

    def is_edge_reserved_reverse(self, from_cell: Cell, to_cell: Cell, time_step: int, by_agent: Optional[int] = None) -> bool:
        owner = self.edge.get((to_cell, from_cell, time_step))
        return owner is not None and owner != by_agent

    def release_agent_future(self, agent_id: int, from_time: int) -> None:
        for key, owner in list(self.vertex.items()):
            _, t = key
            if owner == agent_id and t >= from_time:
                del self.vertex[key]
        for key, owner in list(self.edge.items()):
            _, _, t = key
            if owner == agent_id and t >= from_time:
                del self.edge[key]

    def clear_expired(self, current_time: int) -> None:
        for key in list(self.vertex):
            _, t = key
            if t < current_time:
                del self.vertex[key]
        for key in list(self.edge):
            _, _, t = key
            if t < current_time:
                del self.edge[key]

    def reservation_delay_estimate(self, path: List[Cell], start_time: int, agent_id: int) -> int:
        delay = 0
        for idx, cell in enumerate(path[:20]):
            t = start_time + idx
            if self.is_cell_reserved(cell, t, by_agent=agent_id):
                delay += 1
            if idx > 0 and self.is_edge_reserved_reverse(path[idx-1], cell, t, by_agent=agent_id):
                delay += 1
        return delay
