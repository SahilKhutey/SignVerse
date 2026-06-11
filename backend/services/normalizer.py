import numpy as np
import cv2
from dataclasses import dataclass
from typing import Tuple


@dataclass
class NormalizedFrame:
    """Standard frame format used by all downstream layers."""
    frame_id: int
    timestamp_ms: int
    rgb: np.ndarray         # (480, 640, 3) float32, [0, 1]
    width: int
    height: int
    source: str             # "webcam" | "upload" | "youtube"
    job_id: str


def normalize_frame(
    frame: np.ndarray, 
    target_w: int = 640, 
    target_h: int = 480
) -> np.ndarray:
    """
    Letterbox resize frame to target dimensions.
    Preserves aspect ratio, pads with black.
    Returns RGB float32 in [0, 1].
    """
    if frame is None:
        return np.zeros((target_h, target_w, 3), dtype=np.float32)
    
    # BGR to RGB
    if len(frame.shape) == 3 and frame.shape[2] == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    h, w = frame.shape[:2]
    
    # Compute scale to fit within target
    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # Create canvas (letterbox)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.float32)
    
    # Center placement
    y_offset = (target_h - new_h) // 2
    x_offset = (target_w - new_w) // 2
    
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized.astype(np.float32) / 255.0
    
    return canvas


def normalize_frame_from_bytes(jpeg_bytes: bytes, target_size=(640, 480)) -> np.ndarray:
    """Normalize frame directly from JPEG bytes (WebSocket path)."""
    np_arr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return normalize_frame(frame, target_size[0], target_size[1])
