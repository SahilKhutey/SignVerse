"""
WebSocket endpoints for live perception streaming.
"""
import asyncio
import json
import base64
import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.services.live_broadcaster import broadcaster

router = APIRouter(prefix="/ws/live", tags=["live"])

@router.websocket("")
async def live_perception_socket(websocket: WebSocket):
    """
    Main live perception WebSocket.
    - Server pushes perception JSON every frame
    - Client can send control messages: {"action": "start"}, {"action": "stop"}
    """
    await websocket.accept()

    # Subscribe to broadcaster
    queue = broadcaster.subscribe()
    last_ping = asyncio.get_event_loop().time()

    # Start streaming if not already
    try:
        if not broadcaster.is_streaming:
            await broadcaster.start_streaming(camera_id=0)
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
        return

    # Send "ready" message
    await websocket.send_json({
        "type": "ready",
        "message": "Live stream active. Sending frames..."
    })

    try:
        while True:
            # Check for client control messages (non-blocking)
            try:
                # We don't want to await receive() forever; use timeout
                control_msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.01
                )
                msg = json.loads(control_msg)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong"})
                elif msg.get("action") == "stop":
                    break
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

            # Wait for next perception frame from broadcaster
            try:
                frame_msg = await asyncio.wait_for(queue.get(), timeout=0.1)
                await websocket.send_json(frame_msg)
            except asyncio.TimeoutError:
                # Send keepalive ping
                now = asyncio.get_event_loop().time()
                if now - last_ping > 5.0:
                    await websocket.send_json({"type": "ping"})
                    last_ping = now

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        broadcaster.unsubscribe(queue)


@router.websocket("/video")
async def live_video_socket(websocket: WebSocket):
    """
    Separate WebSocket for the raw video feed.
    Sends JPEG frames as binary.
    """
    await websocket.accept()

    try:
        if not broadcaster.is_streaming:
            await broadcaster.start_streaming(camera_id=0)
    except Exception as e:
        await websocket.close()
        return

    # Read raw frames from the camera and send as JPEG
    loop = asyncio.get_event_loop()

    while True:
        if not broadcaster.is_streaming:
            break

        try:
            ret, frame = await loop.run_in_executor(None, broadcaster.cap.read)
            if not ret:
                await asyncio.sleep(0.01)
                continue

            # Resize for bandwidth
            frame_small = cv2.resize(frame, (640, 480))

            # Encode as JPEG
            _, buf = cv2.imencode('.jpg', frame_small, [cv2.IMWRITE_JPEG_QUALITY, 75])

            # Send binary
            await websocket.send_bytes(buf.tobytes())

            # ~25 FPS
            await asyncio.sleep(1.0 / 25)

        except Exception:
            break
