import json
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.database import MotionSession, MotionFrame
from .kinematics.bvh_writer import write_bvh
from .kinematics.skeleton import SKELETON

def export_json(session: MotionSession, db: Session) -> dict:
    """Export full session as Universal Motion JSON (schema v1)."""
    frames = (db.query(MotionFrame)
              .filter_by(session_id=session.id)
              .order_by(MotionFrame.frame_idx)
              .all())

    return {
        "schema": "signverse-motion-v1",
        "session_id": session.id,
        "session_name": session.name,
        "action_label": session.action_label,
        "source_type": session.source_type,
        "fps": session.fps,
        "frame_count": session.frame_count,
        "duration_s": session.duration_s,
        "avg_confidence": session.avg_confidence,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "frames": [
            {
                "frame_idx": f.frame_idx,
                "timestamp_ms": f.timestamp_ms,
                "confidence": f.confidence_mean,
                "perception": json.loads(f.perception_json),
                "kinematics": json.loads(f.kinematics_json),
            }
            for f in frames
        ]
    }

def export_bvh_string(session: MotionSession, db: Session) -> str:
    """Export session as BVH file content (string)."""
    frames = (db.query(MotionFrame)
              .filter_by(session_id=session.id)
              .order_by(MotionFrame.frame_idx)
              .all())
    kin_frames = [json.loads(f.kinematics_json) for f in frames]
    return write_bvh(kin_frames, session.fps, session.name)

def export_robot_json(session: MotionSession, db: Session) -> dict:
    """Export session as Robot Trajectory JSON (signverse-robot-v1)."""
    frames = (db.query(MotionFrame)
              .filter_by(session_id=session.id)
              .order_by(MotionFrame.frame_idx)
              .all())

    joint_names = list(SKELETON.keys())
    trajectories = {j: [] for j in joint_names}
    quaternions = {j: [] for j in joint_names}
    velocities = {j: [] for j in joint_names}
    timestamps = []

    for f in frames:
        kin = json.loads(f.kinematics_json)
        timestamps.append(f.timestamp_ms)
        for j in joint_names:
            trajectories[j].append(kin["euler_deg"].get(j, [0.0, 0.0, 0.0]))
            quaternions[j].append(kin["quaternions"].get(j, [1.0, 0.0, 0.0, 0.0]))
            velocities[j].append(kin["velocities"].get(j, [0.0, 0.0, 0.0]))

    return {
        "schema": "signverse-robot-v1",
        "session_id": session.id,
        "session_name": session.name,
        "action_label": session.action_label,
        "fps": session.fps,
        "joint_names": joint_names,
        "trajectories": trajectories,
        "quaternions": quaternions,
        "timestamps_ms": timestamps,
        "velocities": velocities,
        "metadata": {
            "frame_count": session.frame_count,
            "duration_s": session.duration_s,
            "source_type": session.source_type,
            "avg_confidence": session.avg_confidence,
            "schema_version": "1.0",
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }
    }
