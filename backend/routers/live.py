"""
WebSocket endpoints for live perception streaming.
"""
import asyncio
import json
import base64
import cv2
import numpy as np
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from backend.services.live_broadcaster import broadcaster
from backend.services.profiling.telemetry_manager import telemetry_manager

router = APIRouter(prefix="/ws/live", tags=["live"])

@router.websocket("")
async def live_perception_socket(websocket: WebSocket):
    """
    Main live perception WebSocket.
    - Server pushes perception JSON every frame
    - Client can send control messages: {"action": "start"}, {"action": "stop"}
    """
    await websocket.accept()
    telemetry_manager.record_ws_connect()

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
        telemetry_manager.record_ws_disconnect()
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
                start_time = time.perf_counter()
                await websocket.send_json(frame_msg)
                telemetry_manager.record_ws_frame(time.perf_counter() - start_time)
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
        telemetry_manager.record_ws_disconnect()


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
            # Query the shared latest frame instead of doing concurrent cv2 read operations
            frame = broadcaster.get_latest_frame()
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            # Letterbox resize BGR frame to 640x480 (preserves aspect ratio with black padding)
            # This matches the perception coordinate system perfectly to align bounding boxes
            h, w = frame.shape[:2]
            scale = min(640 / w, 480 / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

            frame_small = np.zeros((480, 640, 3), dtype=np.uint8)
            y_offset = (480 - new_h) // 2
            x_offset = (640 - new_w) // 2
            frame_small[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

            # Encode as JPEG
            _, buf = cv2.imencode('.jpg', frame_small, [cv2.IMWRITE_JPEG_QUALITY, 75])

            # Send binary
            await websocket.send_bytes(buf.tobytes())

            # ~25 FPS
            await asyncio.sleep(1.0 / 25)

        except Exception:
            break
