from __future__ import annotations

from typing import Dict, List, Optional

from .models import Bid, SimulationConfig, Task


class AuctionProtocol:
    def __init__(self, config: SimulationConfig):
        self.config = config

    def run(self, agents, task_pool, planner, reservation_table, current_time: int, metrics) -> None:
        # Synchronous deterministic auction phase. This is the explicit race-condition fix:
        # all bids are computed first; then exactly one winner can atomically claim a task.
        for task in list(task_pool.unassigned()):
            bids: List[Bid] = []
            for agent in agents:
                if agent.can_bid():
                    bid = agent.compute_bid(task, planner, reservation_table, current_time, self.config)
                    if bid is not None:
                        bids.append(bid)
                        metrics.log_event(current_time, "TASK_BID_SUBMITTED", agent.agent_id, task_id=task.task_id, details=f"bid={bid.value:.2f}")
            if not bids:
                continue
            bids.sort(key=lambda b: (b.value, b.agent_id))
            winner = bids[0]
            if task_pool.assign_task(task.task_id, winner.agent_id):
                winning_agent = next(a for a in agents if a.agent_id == winner.agent_id)
                winning_agent.assign_task(task.task_id)
                metrics.log_event(
                    current_time,
                    "TASK_ASSIGNED",
                    winner.agent_id,
                    task_id=task.task_id,
                    details=f"winner=A{winner.agent_id}, cost={winner.value:.2f}, components={winner.components}",
                    resolution="lowest bid; lowest agent_id tie-breaker",
                )
