import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.db.models import Case, User
from backend.app.security.auth import get_optional_current_user
from backend.app.security.permissions import require_case_access
from backend.app.services.stream_bus import event_bus

router = APIRouter(prefix="/cases", tags=["stream"])


@router.get("/{case_id}/stream")
async def stream_case_events(
    case_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_optional_current_user),
):
    """Server-Sent Events (SSE) stream for real-time case updates."""
    # Verify case exists
    c_res = await session.execute(select(Case).where(Case.id == case_id))
    case = c_res.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user:
        require_case_access(case, current_user)

    async def event_generator():
        queue = await event_bus.subscribe(case_id)
        # Yield initial connected event
        yield f"event: connected\ndata: {json.dumps({'case_id': case_id, 'status': 'connected'})}\n\n"
        try:
            while True:
                # Wait for next event or heartbeat
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: message\ndata: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(case_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
