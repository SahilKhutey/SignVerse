"""
HOI API Router — Human-Object Interaction data endpoints.

GET /api/hoi/{session_id}/timeline   — chronological HOI event list
GET /api/hoi/{session_id}/objects    — unique tracked objects + trajectories
GET /api/hoi/{session_id}/stats      — session-level HOI statistics
GET /api/hoi/{session_id}/summary    — combined scene summary card
"""
import json
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.models.database import (
    get_db, MotionSession,
    ObjectTrajectory, HandObjectInteractionRecord,
)

router = APIRouter(prefix="/api/hoi", tags=["hoi"])


def _get_session_or_404(session_id: str, db: Session) -> MotionSession:
    s = db.query(MotionSession).filter_by(id=session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return s


# ─── Timeline ──────────────────────────────────────────────────── #

@router.get("/{session_id}/timeline")
async def get_hoi_timeline(
    session_id: str,
    min_confidence: float = 0.0,
    interaction_type: str = None,
    hand: str = None,
    db: Session = Depends(get_db),
):
    """
    Chronological list of all HOI events for a session.
    Filterable by confidence, interaction type, and hand.
    """
    _get_session_or_404(session_id, db)

    q = (db.query(HandObjectInteractionRecord)
         .filter_by(session_id=session_id)
         .order_by(HandObjectInteractionRecord.frame_id))

    if min_confidence > 0:
        q = q.filter(HandObjectInteractionRecord.confidence >= min_confidence)
    if interaction_type:
        q = q.filter(HandObjectInteractionRecord.interaction_type == interaction_type.upper())
    if hand:
        q = q.filter(HandObjectInteractionRecord.hand == hand.lower())

    rows = q.all()

    return {
        "session_id": session_id,
        "total_events": len(rows),
        "events": [
            {
                "frame_id":        r.frame_id,
                "timestamp_ms":    r.timestamp_ms,
                "hand":            r.hand,
                "hand_gesture":    r.hand_gesture,
                "object_class":    r.object_class,
                "object_track_id": r.object_track_id,
                "interaction_type":r.interaction_type,
                "confidence":      r.confidence,
                "distance_3d":     r.distance_3d,
                "duration_frames": r.duration_frames,
                "contact_point":   [r.contact_x, r.contact_y, r.contact_z],
                "obj_position_3d": [r.obj_pos_x, r.obj_pos_y, r.obj_pos_z],
            }
            for r in rows
        ],
    }


# ─── Objects ───────────────────────────────────────────────────── #

@router.get("/{session_id}/objects")
async def get_scene_objects(session_id: str, db: Session = Depends(get_db)):
    """
    Return all uniquely tracked objects in this session
    with their full 3D trajectory and interaction summary.
    """
    _get_session_or_404(session_id, db)

    traj_rows = (db.query(ObjectTrajectory)
                 .filter_by(session_id=session_id)
                 .order_by(ObjectTrajectory.track_id, ObjectTrajectory.frame_id)
                 .all())

    # Group by track_id
    tracks: dict = defaultdict(list)
    for r in traj_rows:
        tracks[r.track_id].append(r)

    hoi_rows = (db.query(HandObjectInteractionRecord)
                .filter_by(session_id=session_id)
                .all())
    hoi_by_track = defaultdict(list)
    for h in hoi_rows:
        hoi_by_track[h.object_track_id].append(h)

    objects_out = []
    for tid, det_rows in tracks.items():
        cls_name  = det_rows[0].class_name
        traj      = [[r.frame_id, [r.pos_x, r.pos_y, r.pos_z]] for r in det_rows]
        confs     = [r.confidence or 0.0 for r in det_rows]
        hois      = hoi_by_track.get(tid, [])
        itype_ctr = Counter(h.interaction_type for h in hois)

        objects_out.append({
            "track_id":       tid,
            "class_name":     cls_name,
            "first_frame":    det_rows[0].frame_id,
            "last_frame":     det_rows[-1].frame_id,
            "frame_count":    len(det_rows),
            "avg_confidence": round(sum(confs)/max(len(confs),1), 3),
            "trajectory":     traj,
            "bbox_first":     [det_rows[0].bbox_x1, det_rows[0].bbox_y1,
                               det_rows[0].bbox_x2, det_rows[0].bbox_y2],
            "interaction_summary": dict(itype_ctr),
            "total_interactions": len(hois),
            "predominant_interaction": itype_ctr.most_common(1)[0][0] if itype_ctr else None,
        })

    return {
        "session_id":     session_id,
        "total_objects":  len(objects_out),
        "unique_classes": list({o["class_name"] for o in objects_out}),
        "objects":        objects_out,
    }


# ─── Stats ─────────────────────────────────────────────────────── #

@router.get("/{session_id}/stats")
async def get_hoi_stats(session_id: str, db: Session = Depends(get_db)):
    """
    Aggregate HOI statistics for the session:
    hold durations, interaction counts, object interaction matrix.
    """
    session = _get_session_or_404(session_id, db)

    hoi_rows = (db.query(HandObjectInteractionRecord)
                .filter_by(session_id=session_id)
                .all())
    traj_rows = (db.query(ObjectTrajectory)
                 .filter_by(session_id=session_id)
                 .all())

    # Interaction type distribution
    itype_ctr = Counter(r.interaction_type for r in hoi_rows)

    # Per-object interaction counts
    obj_hoi = Counter(r.object_class for r in hoi_rows)

    # Hold events — find longest hold per object
    hold_types = {"HOLDING","LIFTING","MOVING","PLACING"}
    hold_events = [r for r in hoi_rows if r.interaction_type in hold_types]
    hold_by_obj = defaultdict(list)
    for h in hold_events:
        hold_by_obj[h.object_class].append(h.duration_frames)

    hold_stats = {
        cls: {
            "total_hold_frames":  sum(durations),
            "max_hold_frames":    max(durations),
            "avg_hold_frames":    round(sum(durations)/len(durations), 1),
            "hold_count":         len(durations),
        }
        for cls, durations in hold_by_obj.items()
    }

    # Unique objects
    unique_classes = list({r.class_name for r in traj_rows})

    return {
        "session_id":            session_id,
        "session_name":          session.name,
        "fps":                   session.fps,
        "frame_count":           session.frame_count,
        "duration_s":            session.duration_s,
        "total_hoi_events":      len(hoi_rows),
        "total_object_detections": len(traj_rows),
        "unique_objects":        unique_classes,
        "primary_object":        getattr(session, "primary_object", None),
        "interaction_distribution": dict(itype_ctr),
        "object_interaction_counts": dict(obj_hoi),
        "hold_statistics":       hold_stats,
        "left_hand_events":      sum(1 for r in hoi_rows if r.hand == "left"),
        "right_hand_events":     sum(1 for r in hoi_rows if r.hand == "right"),
    }


# ─── Summary ───────────────────────────────────────────────────── #

@router.get("/{session_id}/summary")
async def get_scene_summary(session_id: str, db: Session = Depends(get_db)):
    """Combined scene card — person + objects + HOI highlights."""
    session = _get_session_or_404(session_id, db)

    unique_objs_json = getattr(session, "unique_objects", None)
    try:
        unique_objs = json.loads(unique_objs_json) if unique_objs_json else []
    except Exception:
        unique_objs = []

    return {
        "session_id":       session_id,
        "session_name":     session.name,
        "action_label":     session.action_label,
        "source_type":      session.source_type,
        "fps":              session.fps,
        "frame_count":      session.frame_count,
        "duration_s":       session.duration_s,
        "avg_confidence":   session.avg_confidence,
        # HOI summary
        "object_count":     getattr(session, "object_count",      0),
        "interaction_count":getattr(session, "interaction_count",  0),
        "unique_objects":   unique_objs,
        "primary_object":   getattr(session, "primary_object",    None),
        # Scene export hints
        "scene_exports_available": [
            "gltf_scene", "glb_scene", "bvh_scene",
            "mujoco_scene", "blender_scene", "usd_scene",
        ],
    }
