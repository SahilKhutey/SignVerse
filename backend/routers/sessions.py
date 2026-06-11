from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from ..models.database import MotionSession, MotionFrame, get_db
from ..services.export_engine import (
    export_json, export_bvh_string, export_robot_json
)

router = APIRouter()

@router.get("/api/sessions")
async def list_sessions(db: Session = Depends(get_db)):
    """List all sessions, newest first."""
    sessions = (db.query(MotionSession)
                .order_by(MotionSession.created_at.desc())
                .all())
    return [_session_dict(s) for s in sessions]

@router.get("/api/sessions/{sid}")
async def get_session(sid: str, db: Session = Depends(get_db)):
    """Get a single session by ID."""
    s = db.get(MotionSession, sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return _session_dict(s)

@router.patch("/api/sessions/{sid}/label")
async def update_label(sid: str, body: dict, db: Session = Depends(get_db)):
    """Update the action label of a session."""
    s = db.get(MotionSession, sid)
    if not s:
        raise HTTPException(404, "Session not found")
    s.action_label = body.get("label", "IDLE")
    db.commit()
    return {"ok": True, "label": s.action_label}

@router.delete("/api/sessions/{sid}")
async def delete_session(sid: str, db: Session = Depends(get_db)):
    """Delete a session and all its frames."""
    s = db.get(MotionSession, sid)
    if s:
        db.delete(s)
        db.commit()
    return {"ok": True}

@router.get("/api/sessions/{sid}/export")
async def export_session(sid: str, fmt: str = "json", db: Session = Depends(get_db)):
    """
    Export a session in the specified format.
    fmt: 'json' | 'bvh' | 'robot'
    """
    s = db.get(MotionSession, sid)
    if not s:
        raise HTTPException(404, "Session not found")

    if fmt == "json":
        data = export_json(s, db)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{s.name}.json"'}
        )

    elif fmt == "bvh":
        bvh_str = export_bvh_string(s, db)
        return Response(
            content=bvh_str.encode(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{s.name}.bvh"'}
        )

    elif fmt == "robot":
        data = export_robot_json(s, db)
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{s.name}.robot.json"'}
        )

    raise HTTPException(400, f"Unknown format: {fmt}")

@router.get("/api/sessions/{sid}/frames")
async def get_frames(
    sid: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get frames for a session with pagination."""
    frames = (db.query(MotionFrame)
              .filter_by(session_id=sid)
              .order_by(MotionFrame.frame_idx)
              .offset(skip).limit(limit).all())
    return [
        {
            "frame_idx": f.frame_idx,
            "timestamp_ms": f.timestamp_ms,
            "confidence": f.confidence_mean,
            "kinematics": json.loads(f.kinematics_json),
            "pose_33": json.loads(f.perception_json).get("pose", []),
            "left_hand_21": json.loads(f.perception_json).get("left_hand", []),
            "right_hand_21": json.loads(f.perception_json).get("right_hand", []),
            "metric_frame": json.loads(f.metric_json) if getattr(f, "metric_json", None) else None,
        }
        for f in frames
    ]

@router.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Aggregate dataset statistics."""
    total_sessions = db.query(MotionSession).count()
    total_frames = db.query(MotionFrame).count()
    avg_conf = db.query(func.avg(MotionFrame.confidence_mean)).scalar() or 0.0
    label_dist = (db.query(
        MotionSession.action_label,
        func.count(MotionSession.id)
    ).group_by(MotionSession.action_label).all())

    return {
        "total_sessions": total_sessions,
        "total_frames": total_frames,
        "avg_confidence": round(float(avg_conf), 3),
        "label_distribution": {k: v for k, v in label_dist},
    }

def _session_dict(s: MotionSession) -> dict:
    """Convert a MotionSession ORM object to a JSON-safe dict."""
    return {
        "id": s.id,
        "name": s.name,
        "source_type": s.source_type,
        "fps": s.fps,
        "frame_count": s.frame_count,
        "duration_s": s.duration_s,
        "action_label": s.action_label,
        "thumbnail_path": s.thumbnail_path,
        "avg_confidence": s.avg_confidence,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
