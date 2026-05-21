from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Set

from .models import Cell


class WarehouseGrid:
    def __init__(self, rows: int, cols: int, obstacles: Iterable[Cell], pickups: Iterable[Cell], dropoffs: Iterable[Cell]):
        self.rows = rows
        self.cols = cols
        self.obstacles: Set[Cell] = set(obstacles)
        self.pickups: List[Cell] = list(pickups)
        self.dropoffs: List[Cell] = list(dropoffs)
        self.occupancy: Dict[Cell, int] = {}

    def in_bounds(self, cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < self.rows and 0 <= c < self.cols

    def is_obstacle(self, cell: Cell) -> bool:
        return cell in self.obstacles

    def is_free_static(self, cell: Cell) -> bool:
        return self.in_bounds(cell) and not self.is_obstacle(cell)

    def is_occupied(self, cell: Cell) -> bool:
        return cell in self.occupancy

    def occupant(self, cell: Cell) -> Optional[int]:
        return self.occupancy.get(cell)

    def valid_move_target(self, cell: Cell) -> bool:
        return self.is_free_static(cell)

    def neighbors(self, cell: Cell, include_wait: bool = True) -> List[Cell]:
        r, c = cell
        candidates = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        if include_wait:
            candidates.append(cell)
        return [x for x in candidates if self.valid_move_target(x)]

    def set_agent_positions(self, positions: Dict[int, Cell]) -> None:
        self.occupancy = {}
        for agent_id, cell in positions.items():
            if not self.valid_move_target(cell):
                raise ValueError(f"Invalid position for agent {agent_id}: {cell}")
            if cell in self.occupancy:
                raise ValueError(f"Collision in occupancy update at {cell}")
            self.occupancy[cell] = agent_id

    def manhattan(self, a: Cell, b: Cell) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def local_congestion(self, cell: Cell, radius: int = 2, capacity: int = 5) -> float:
        count = 0
        cr, cc = cell
        for pos in self.occupancy:
            if abs(pos[0] - cr) + abs(pos[1] - cc) <= radius:
                count += 1
        return count / max(capacity, 1)

    def all_free_cells(self) -> List[Cell]:
        return [(r, c) for r in range(self.rows) for c in range(self.cols) if self.valid_move_target((r, c))]


def default_layout(rows: int, cols: int):
    obstacles = set()
    # Shelving blocks with corridors. Keep enough routes for MAPF.
    for r in range(3, rows - 3):
        if r % 5 == 0:
            continue
        for c in range(5, cols - 5):
            if c % 6 in (0, 1, 2):
                obstacles.add((r, c))
    # small bottleneck wall with gaps
    mid = rows // 2
    for c in range(2, cols - 2):
        if c not in (3, cols // 2, cols - 4):
            obstacles.add((mid, c))
    pickups = [(1, 1), (1, cols - 2), (rows - 2, 1), (rows - 2, cols - 2)]
    dropoffs = [(1, cols // 2), (rows - 2, cols // 2), (rows // 2, 1), (rows // 2, cols - 2)]
    obstacles -= set(pickups)
    obstacles -= set(dropoffs)
    return obstacles, pickups, dropoffs
