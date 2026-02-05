"""
In-memory SSE broadcaster for real-time events per tenant.
Replaces Pusher/Soketi for server-sent events.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """
    In-memory broadcaster: maintains per-tenant queues and delivers
    (event_name, data) to all subscribers for that tenant.
    """

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue[tuple[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, tenant_id: str) -> "asyncio.Queue[tuple[str, Any]]":
        """Create a queue for this tenant; caller must remove it on disconnect."""
        q: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        async with self._lock:
            if tenant_id not in self._queues:
                self._queues[tenant_id] = []
            self._queues[tenant_id].append(q)
        logger.debug("SSE subscribe tenant_id=%s queues_count=%s", tenant_id, len(self._queues.get(tenant_id, [])))
        return q

    async def unsubscribe(self, tenant_id: str, queue: asyncio.Queue[tuple[str, Any]]) -> None:
        """Remove a subscriber queue for this tenant."""
        async with self._lock:
            if tenant_id in self._queues:
                try:
                    self._queues[tenant_id].remove(queue)
                except ValueError:
                    pass
                if not self._queues[tenant_id]:
                    del self._queues[tenant_id]

    def broadcast(self, tenant_id: str, event_name: str, data: Any) -> None:
        """
        Send an event to all subscribers for this tenant.
        Data is serialized to JSON if not already a string.
        """
        payload = data if isinstance(data, str) else json.dumps(data, default=str)
        queues = self._queues.get(tenant_id) or []
        for q in queues:
            try:
                q.put_nowait((event_name, payload))
            except asyncio.QueueFull:
                logger.warning("SSE queue full for tenant_id=%s, dropping event %s", tenant_id, event_name)


# Singleton used by routes and tasks
_sse_broadcaster: SSEBroadcaster | None = None


def get_sse_broadcaster() -> SSEBroadcaster:
    """Return the global SSE broadcaster instance."""
    global _sse_broadcaster
    if _sse_broadcaster is None:
        _sse_broadcaster = SSEBroadcaster()
    return _sse_broadcaster


def notify_sse(tenant_id: str, event_name: str, data: Any) -> None:
    """
    Notify all SSE subscribers for the given tenant.
    Use this instead of pusher_client.trigger(...).
    """
    get_sse_broadcaster().broadcast(tenant_id, event_name, data)
