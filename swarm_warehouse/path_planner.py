from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

from .grid import WarehouseGrid
from .models import Cell
from .reservation import ReservationTable


class PathPlanner:
    def __init__(self, grid: WarehouseGrid):
        self.grid = grid

    def a_star(self, start: Cell, goal: Cell) -> Optional[List[Cell]]:
        open_heap: List[Tuple[float, int, Cell]] = []
        heapq.heappush(open_heap, (self.grid.manhattan(start, goal), 0, start))
        came: Dict[Cell, Cell] = {}
        g: Dict[Cell, int] = {start: 0}
        counter = 0
        closed = set()
        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            if current == goal:
                return self._reconstruct_cell(came, current)
            closed.add(current)
            for nb in self.grid.neighbors(current, include_wait=False):
                tentative = g[current] + 1
                if tentative < g.get(nb, 10**9):
                    came[nb] = current
                    g[nb] = tentative
                    counter += 1
                    f = tentative + self.grid.manhattan(nb, goal)
                    heapq.heappush(open_heap, (f, counter, nb))
        return None

    def cooperative_a_star(
        self,
        start: Cell,
        goal: Cell,
        start_time: int,
        reservations: ReservationTable,
        agent_id: int,
        max_time_expansion: int = 160,
        congestion_weight: float = 0.5,
    ) -> Optional[List[Cell]]:
        State = Tuple[int, int, int]
        start_state: State = (start[0], start[1], start_time)
        open_heap: List[Tuple[float, int, State]] = []
        heapq.heappush(open_heap, (self.grid.manhattan(start, goal), 0, start_state))
        came: Dict[State, State] = {}
        g: Dict[State, float] = {start_state: 0.0}
        closed = set()
        counter = 0
        latest_time = start_time + max_time_expansion

        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            if current in closed:
                continue
            r, c, t = current
            cell = (r, c)
            if cell == goal:
                return self._reconstruct_state(came, current)
            closed.add(current)
            if t >= latest_time:
                continue
            for nb in self.grid.neighbors(cell, include_wait=True):
                nt = t + 1
                if reservations.is_cell_reserved(nb, nt, by_agent=agent_id):
                    continue
                if reservations.is_edge_reserved_reverse(cell, nb, nt, by_agent=agent_id):
                    continue
                nstate: State = (nb[0], nb[1], nt)
                move_cost = 1.0
                if nb == cell:
                    move_cost += 0.3
                move_cost += congestion_weight * self.grid.local_congestion(nb)
                tentative = g[current] + move_cost
                if tentative < g.get(nstate, 10**18):
                    came[nstate] = current
                    g[nstate] = tentative
                    counter += 1
                    h = self.grid.manhattan(nb, goal)
                    heapq.heappush(open_heap, (tentative + h, counter, nstate))
        return None

    def _reconstruct_cell(self, came: Dict[Cell, Cell], current: Cell) -> List[Cell]:
        path = [current]
        while current in came:
            current = came[current]
            path.append(current)
        return list(reversed(path))

    def _reconstruct_state(self, came: Dict[Tuple[int, int, int], Tuple[int, int, int]], current: Tuple[int, int, int]) -> List[Cell]:
        path = [(current[0], current[1])]
        while current in came:
            current = came[current]
            path.append((current[0], current[1]))
        return list(reversed(path))
