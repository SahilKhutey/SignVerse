import cv2
from pathlib import Path
from typing import Tuple

def get_video_info(path: str) -> dict:
    """Read metadata information from video container"""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {}
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    }
    cap.release()
    if info["fps"]:
        info["duration_sec"] = info["frame_count"] / info["fps"]
    return info

def validate_video(path: Path) -> Tuple[bool, str]:
    """Inspect file system size constraints and open container to validate codec integrity"""
    if not path.exists():
        return False, "File not found"
    if path.stat().st_size > 500 * 1024 * 1024:
        return False, "File exceeds size limits (max 500MB)"
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return False, "Unable to read video metadata from file container"
    cap.release()
    return True, "OK"
