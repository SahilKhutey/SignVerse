import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.frame_processor import FrameProcessor

router = APIRouter(prefix="/api/stream", tags=["stream"])

@router.websocket("/camera")
async def stream_camera(websocket: WebSocket):
    """WebSocket handler for streaming live camera frames with real-time pose extraction"""
    await websocket.accept()
    processor = FrameProcessor(source="camera", filename="live_stream")
    duration = 60
    
    try:
        # Accept configuration payload from client (e.g. session duration)
        try:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=2.0)
            duration = int(data.get("duration", 60))
        except (asyncio.TimeoutError, Exception):
            pass

        await websocket.send_json(
            {"type": "status", "payload": {"msg": "Camera recording initialized", "duration": duration}}
        )

        # Iterate over camera generator yields
        async for pose_frame in processor.stream_camera(duration_sec=duration):
            await websocket.send_json(
                {
                    "type": "frame",
                    "payload": pose_frame.model_dump(),
                }
            )
            # Throttle stream back to standard frame rate (~30 FPS)
            await asyncio.sleep(1 / 30)

        # Broadcast termination and session ID
        await websocket.send_json(
            {
                "type": "complete",
                "payload": {
                    "session_id": processor.session_id,
                    "frame_count": len(processor.frames),
                },
            }
        )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "payload": {"msg": str(e)}})
        except Exception:
            pass
    finally:
        processor.extractor.close()
