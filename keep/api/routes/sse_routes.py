"""
SSE (Server-Sent Events) endpoint for real-time updates.
Replaces Pusher/WebSocket; supports no-auth when AUTH_TYPE=noauth.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from keep.api.core.dependencies import get_sse_authenticated_entity
from keep.api.sse import get_sse_broadcaster
from keep.identitymanager.authenticatedentity import AuthenticatedEntity

logger = logging.getLogger(__name__)

router = APIRouter()

SSE_HEARTBEAT_INTERVAL = 30


def _format_sse(event: str, data: str) -> str:
    """Format a single SSE message: event: X\ndata: Y\n\n"""
    return f"event: {event}\ndata: {data}\n\n"


async def _sse_stream(
    request: Request,
    tenant_id: str,
):
    broadcaster = get_sse_broadcaster()
    queue = await broadcaster.subscribe(tenant_id)
    try:
        yield _format_sse("connected", json.dumps({"tenant_id": tenant_id}))
        last_heartbeat = asyncio.get_event_loop().time()
        while True:
            try:
                wait_until = last_heartbeat + SSE_HEARTBEAT_INTERVAL
                now = asyncio.get_event_loop().time()
                timeout = max(0.1, wait_until - now)
                try:
                    event_name, data = await asyncio.wait_for(
                        queue.get(), timeout=timeout
                    )
                    yield _format_sse(event_name, data)
                except asyncio.TimeoutError:
                    try:
                        if await request.is_disconnected():
                            break
                    except Exception:
                        break
                    yield _format_sse("heartbeat", "")
                    last_heartbeat = asyncio.get_event_loop().time()
            except asyncio.CancelledError:
                break
    finally:
        await broadcaster.unsubscribe(tenant_id, queue)


@router.get("/events")
async def sse_events(
    request: Request,
    authenticated_entity: AuthenticatedEntity = Depends(get_sse_authenticated_entity),
):
    """
    Stream server-sent events for the authenticated tenant.
    When AUTH_TYPE=noauth and no credentials are sent, uses default tenant.
    Optional query param: token=... for Bearer (EventSource cannot send headers).
    """
    tenant_id = authenticated_entity.tenant_id
    logger.info("SSE client connected tenant_id=%s", tenant_id)
    return StreamingResponse(
        _sse_stream(request, tenant_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
