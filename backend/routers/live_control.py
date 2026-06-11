"""
REST endpoints to control live streaming from the frontend.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.live_broadcaster import broadcaster


router = APIRouter(prefix="/api/live", tags=["live-control"])


class LiveStatus(BaseModel):
    is_streaming: bool
    server_fps: float
    subscriber_count: int
    latest_frame_id: int
    latest_intent: str
    latest_action: str
    latest_expression: str


@router.get("/status", response_model=LiveStatus)
async def get_status():
    """Get current live streaming status."""
    if not broadcaster.latest_result:
        return LiveStatus(
            is_streaming=broadcaster.is_streaming,
            server_fps=0.0,
            subscriber_count=len(broadcaster.clients),
            latest_frame_id=0,
            latest_intent="UNKNOWN",
            latest_action="IDLE",
            latest_expression="NEUTRAL",
        )

    return LiveStatus(
        is_streaming=broadcaster.is_streaming,
        server_fps=round(broadcaster.fps_counter["fps"], 1),
        subscriber_count=len(broadcaster.clients),
        latest_frame_id=broadcaster.latest_result.frame_id,
        latest_intent=broadcaster.latest_result.primary_intent,
        latest_action=broadcaster.latest_result.primary_action,
        latest_expression=broadcaster.latest_result.expression,
    )


@router.post("/start")
async def start_stream(camera_id: int = 0):
    """Start the live capture stream."""
    try:
        if not broadcaster.is_streaming:
            await broadcaster.start_streaming(camera_id=camera_id)
        return {"status": "started", "camera_id": camera_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/stop")
async def stop_stream():
    """Stop the live capture stream."""
    await broadcaster.stop_streaming()
    return {"status": "stopped"}


@router.get("/snapshot")
async def get_snapshot():
    """Get the latest perception result as JSON (for polling fallback)."""
    if not broadcaster.latest_result:
        raise HTTPException(404, "No frames yet")

    return broadcaster._serialize_result(broadcaster.latest_result)
