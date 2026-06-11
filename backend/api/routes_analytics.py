"""Analytics + action segmentation endpoints."""
import json
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.database import db
from backend.core.action_segmenter import ActionSegmenter
from backend.core.motion_metrics import MotionMetrics
from backend.config import settings

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class SegmentRequest(BaseModel):
    session_id: str


@router.post("/segment")
async def segment_session(req: SegmentRequest):
    """Run action segmentation on a session."""
    session = db.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    skeleton_path = session.get("skeleton_json_path")
    if not skeleton_path or not Path(skeleton_path).exists():
        raise HTTPException(404, "Skeleton data not found")

    with open(skeleton_path) as f:
        data = json.load(f)
    frames = data.get("frames", [])
    if not frames:
        raise HTTPException(400, "No frames")

    landmarks_seq = [f.get("pose_33", []) for f in frames]
    fps = session.get("fps", 30)

    segmenter = ActionSegmenter(fps=fps)
    segments = segmenter.segment_sequence(landmarks_seq)
    segments_dict = [s.to_dict() for s in segments]

    # Persist
    db.save_segments(req.session_id, segments_dict)

    return {
        "session_id": req.session_id,
        "segment_count": len(segments),
        "segments": segments_dict,
    }


@router.get("/segments/{session_id}")
async def get_segments(session_id: str):
    """Get stored segments for a session."""
    return db.get_segments(session_id)


@router.get("/dataset")
async def full_dataset_analytics():
    """Full dataset analytics."""
    metrics = MotionMetrics()
    return metrics.compute_full_analytics()


@router.get("/session/{session_id}")
async def session_analytics(session_id: str):
    """Detailed analytics for single session."""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    metrics = MotionMetrics()
    return metrics._analyze_session(session)
