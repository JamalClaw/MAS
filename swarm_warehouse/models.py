from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any

Cell = Tuple[int, int]


class AgentState(Enum):
    IDLE = auto()
    BIDDING = auto()
    ASSIGNED = auto()
    MOVING_TO_PICKUP = auto()
    PICKING_UP = auto()
    MOVING_TO_DROPOFF = auto()
    DELIVERING = auto()
    WAITING = auto()
    REPLANNING = auto()
    DEADLOCK_RECOVERY = auto()


class TaskState(Enum):
    UNASSIGNED = auto()
    ASSIGNED = auto()
    COMPLETED = auto()


class Performative(Enum):
    INFORM = auto()
    REQUEST = auto()
    CFP = auto()
    PROPOSE = auto()
    ACCEPT_PROPOSAL = auto()
    REJECT_PROPOSAL = auto()


class ReservationType(Enum):
    VERTEX = auto()
    EDGE = auto()


class ConflictType(Enum):
    VERTEX_CONFLICT = auto()
    EDGE_CONFLICT = auto()
    BLOCKING_CONFLICT = auto()
    RESERVATION_CONFLICT = auto()


class ActionType(Enum):
    WAIT = auto()
    MOVE = auto()
    PICKUP = auto()
    DELIVER = auto()
    NONE = auto()


@dataclass
class Task:
    task_id: str
    pickup: Cell
    dropoff: Cell
    creation_time: int
    state: TaskState = TaskState.UNASSIGNED
    assigned_agent_id: Optional[int] = None
    pickup_time: Optional[int] = None
    completion_time: Optional[int] = None


@dataclass(frozen=True)
class Reservation:
    agent_id: int
    cell: Cell
    time_step: int
    reservation_type: ReservationType
    previous_cell: Optional[Cell] = None
    expires_at: Optional[int] = None


@dataclass
class Message:
    message_id: str
    sender_id: Any
    receiver_id: Any
    performative: Performative
    content: Dict[str, Any]
    timestamp: int
    conversation_id: str


@dataclass
class MovementIntent:
    agent_id: int
    current_cell: Cell
    next_cell: Cell
    action: ActionType


@dataclass
class Conflict:
    conflict_type: ConflictType
    involved_agents: Tuple[int, ...]
    cell: Optional[Cell] = None
    description: str = ""


@dataclass
class Bid:
    agent_id: int
    task_id: str
    value: float
    components: Dict[str, float] = field(default_factory=dict)


@dataclass
class SimulationConfig:
    grid_rows: int = 16
    grid_cols: int = 24
    num_agents: int = 6
    task_generation_rate: float = 0.18
    max_time_steps: int = 600
    random_seed: int = 7
    wait_threshold: int = 5
    congestion_threshold: float = 0.7
    reservation_horizon: int = 18
    agent_speed: int = 1
    alpha_distance: float = 1.0
    beta_congestion: float = 2.0
    gamma_workload: float = 5.0
    delta_reservation: float = 1.5
    priority_carrying_weight: float = 100.0
    priority_waiting_weight: float = 5.0
    priority_progress_weight: float = 2.0
    priority_id_weight: float = 0.001
    enable_pygame: bool = False
    render_delay_ms: int = 80
    scenario: str = "baseline"
