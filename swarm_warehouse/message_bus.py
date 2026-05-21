from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List

from .models import Message


class MessageBus:
    def __init__(self):
        self.outbox: List[Message] = []
        self.inbox: Dict[Any, List[Message]] = defaultdict(list)
        self.counter = 0

    def send(self, message: Message) -> None:
        self.outbox.append(message)

    def deliver(self, agent_ids: List[int]) -> None:
        self.inbox.clear()
        for msg in self.outbox:
            if msg.receiver_id == "ALL":
                for aid in agent_ids:
                    if aid != msg.sender_id:
                        self.inbox[aid].append(msg)
            else:
                self.inbox[msg.receiver_id].append(msg)
        self.outbox.clear()

    def receive(self, agent_id: int) -> List[Message]:
        return list(self.inbox.get(agent_id, []))
