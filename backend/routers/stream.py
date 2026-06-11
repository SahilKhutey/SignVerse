import cv2
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.services.perception_pipeline import PerceptionPipeline
from backend.services.perception.overlay import draw_pose_overlay

router = APIRouter(prefix="/ws", tags=["stream"])

@router.websocket("/camera")
async def camera_stream(
    websocket: WebSocket,
    fps: int = Query(25, ge=1, le=60)
):
    """Stream webcam frames as JPEG bytes over WebSocket."""
    await websocket.accept()
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        await websocket.send_json({"error": "Cannot open camera"})
        await websocket.close()
        return
    
    frame_delay = 1.0 / fps
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Resize for bandwidth
            frame = cv2.resize(frame, (640, 480))
            
            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            
            # Send binary
            await websocket.send_bytes(buffer.tobytes())
            
            # Frame rate control
            await asyncio.sleep(frame_delay)
            
    except WebSocketDisconnect:
        pass
    finally:
        cap.release()


@router.websocket("/perception")
async def perception_stream(
    websocket: WebSocket,
    fps: int = Query(25, ge=1, le=60)
):
    """Stream annotated 2D overlay frames containing pose and YOLO object tracking."""
    await websocket.accept()
    pipeline = PerceptionPipeline()
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        await websocket.send_json({"error": "Cannot open camera"})
        await websocket.close()
        return
        
    frame_delay = 1.0 / fps
    frame_id = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Run holistic + YOLO on BGR image
            res = pipeline.process_frame(frame, frame_id, int(frame_id * frame_delay * 1000))
            
            # Annotate BGR frame
            annotated = draw_pose_overlay(frame, res)
            
            # Encode
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            await websocket.send_bytes(buffer.tobytes())
            
            frame_id += 1
            await asyncio.sleep(frame_delay)
            
    except WebSocketDisconnect:
        pass
    finally:
        cap.release()
