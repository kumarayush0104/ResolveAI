import asyncio
import json
from typing import Dict, List, Any


class EventBus:
    """In-memory pub/sub event bus for case-level SSE streaming."""

    def __init__(self):
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, case_id: str) -> asyncio.Queue:
        """Register a new listener queue for a given case_id."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            if case_id not in self._subscribers:
                self._subscribers[case_id] = []
            self._subscribers[case_id].append(queue)
        return queue

    async def unsubscribe(self, case_id: str, queue: asyncio.Queue) -> None:
        """Remove a listener queue when the client disconnects."""
        async with self._lock:
            if case_id in self._subscribers:
                self._subscribers[case_id] = [q for q in self._subscribers[case_id] if q is not queue]
                if not self._subscribers[case_id]:
                    del self._subscribers[case_id]

    async def broadcast(self, case_id: str, event_data: Dict[str, Any]) -> None:
        """Broadcast an event to all active SSE subscribers for this case."""
        async with self._lock:
            queues = list(self._subscribers.get(case_id, []))

        for queue in queues:
            try:
                queue.put_nowait(event_data)
            except Exception:
                pass


event_bus = EventBus()
