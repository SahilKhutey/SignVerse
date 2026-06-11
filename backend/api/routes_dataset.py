import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from backend.core.database import db
from backend.core.bvh_writer import BVHWriter
from backend.core.retargeter import RobotRetargeter
from backend.config import settings

router = APIRouter(prefix="/api/dataset", tags=["dataset"])

class LabelRequest(BaseModel):
    action_label: str
    notes: str = ""

@router.get("/list")
async def list_sessions(limit: int = 50):
    """Retrieve list of captured movement sessions"""
    return db.list_sessions(limit=limit)

@router.get("/stats")
async def dataset_stats():
    """Retrieve overall dataset frame counts and stats summaries"""
    return db.stats()

@router.get("/{session_id}")
async def get_session(session_id: str):
    """Retrieve metadata of a specific session"""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Deletes session metadata and related database frames entries"""
    success = db.delete_session(session_id)
    if not success:
        raise HTTPException(404, "Session not found")
    return {"deleted": session_id}

@router.post("/{session_id}/label")
async def label_session(session_id: str, req: LabelRequest):
    """Assigns an action label tag and notes to a session"""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    db.label_session(session_id, req.action_label, req.notes)
    return {"session_id": session_id, "action_label": req.action_label}

@router.get("/{session_id}/bvh")
async def export_bvh(session_id: str):
    """Generates and downloads a Blender-compatible BVH coordinate file"""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    skeleton_path = session.get("skeleton_json_path")
    if not skeleton_path or not Path(skeleton_path).exists():
        raise HTTPException(404, "Skeleton landmarks file not found")

    with open(skeleton_path) as f:
        data = json.load(f)

    # MediaPipe pose frames
    frames_landmarks = []
    for frame in data.get("frames", []):
        # MediaPipe Holistic landmarks are in pose_33 list
        pose_data = frame.get("pose_33", [])
        if not pose_data:
            # Fallback to key index names
            pose_data = frame.get("landmarks_33", [])
        frames_landmarks.append(pose_data)
        
    if not frames_landmarks:
        raise HTTPException(400, "Session contains no pose landmark data to write")

    # Generate BVH
    out_path = settings.export_dir / f"{session_id}.bvh"
    writer = BVHWriter(fps=int(session.get("fps", 30)))
    writer.generate(frames_landmarks, str(out_path))

    with open(out_path, "rb") as f:
        content = f.read()
        
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.bvh"},
    )

@router.get("/{session_id}/robot-dataset")
async def export_robot_dataset(session_id: str):
    """Formats and exports humanoid joint space angles (radians) for ROS2/Isaac Sim"""
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    skeleton_path = session.get("skeleton_json_path")
    if not skeleton_path or not Path(skeleton_path).exists():
        raise HTTPException(404, "Skeleton landmarks file not found")

    with open(skeleton_path) as f:
        data = json.load(f)

    frames_landmarks = []
    for frame in data.get("frames", []):
        pose_data = frame.get("pose_33", [])
        if not pose_data:
            pose_data = frame.get("landmarks_33", [])
        frames_landmarks.append(pose_data)
        
    fps = session.get("fps", 30)

    retargeter = RobotRetargeter()
    dataset = retargeter.retarget_sequence(frames_landmarks, fps=fps)
    dataset["metadata"]["source_session_id"] = session_id
    dataset["metadata"]["source_action_label"] = session.get("action_label")

    return dataset
