from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Landmark(BaseModel):
    x: float
    y: float
    z: float = 0.0
    v: float = 1.0  # Visibility/confidence

class PoseFrame(BaseModel):
    frame_id: int
    timestamp: float
    pose_33: List[Landmark] = Field(default_factory=list)
    left_hand_21: List[Landmark] = Field(default_factory=list)
    right_hand_21: List[Landmark] = Field(default_factory=list)
    face_468: List[Landmark] = Field(default_factory=list)  # Sampled face
    confidence: float = 0.0

class SessionMetadata(BaseModel):
    session_id: str
    source: str  # "upload" | "camera" | "youtube"
    filename: str
    fps: float
    frame_count: int
    duration_sec: float
    created_at: datetime
    status: str = "processing"  # processing | ready | failed

class ProcessRequest(BaseModel):
    session_id: str
    smooth: bool = True

class ProcessResponse(BaseModel):
    session_id: str
    status: str
    frame_count: int
    duration_sec: float
    download_json: Optional[str] = None

class WebSocketMessage(BaseModel):
    type: str  # "frame" | "status" | "error" | "complete"
    payload: dict
