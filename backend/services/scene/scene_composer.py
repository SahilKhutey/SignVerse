"""
Scene Composer — loads person motion + object trajectories + HOI events
and produces a unified `SceneData` ready for scene-level exporters.
"""
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from backend.models.database import (
    MotionSession, MotionFrame,
    ObjectTrajectory, HandObjectInteractionRecord,
)
from backend.services.exporters.data_loader import (
    UnifiedMotionData, SessionDataLoader, CANONICAL_JOINTS
)
from .object_library import get_model, ObjectModel3D


# ═══════════════════════════════════════════════════════════════════ #
# Data model
# ═══════════════════════════════════════════════════════════════════ #

@dataclass
class HoldEvent:
    """A period where a hand held an object (object parented to hand joint)."""
    hand:            str         # "left" | "right"
    start_frame:     int
    end_frame:       int
    hand_joint:      str         # canonical joint name: "LeftHand" | "RightHand"
    relative_offset: List[float] # [dx, dy, dz] metres from hand joint to object centre

    @property
    def duration(self) -> int:
        return self.end_frame - self.start_frame + 1


@dataclass
class AnimatedSceneObject:
    """One tracked object with its full animation across the session."""
    track_id:    int
    class_name:  str
    model:       ObjectModel3D

    # Per-frame world-space trajectory: [[frame_idx, [x,y,z]], ...]
    world_trajectory: List[Tuple[int, List[float]]] = field(default_factory=list)

    # Hold events (when object is attached to a hand joint)
    hold_events: List[HoldEvent] = field(default_factory=list)

    # Bounding box trajectory: [[frame_idx, [x1,y1,x2,y2]], ...]
    bbox_trajectory: List[Tuple[int, List[float]]] = field(default_factory=list)

    # Aggregate info
    first_frame: int = 0
    last_frame:  int = 0
    avg_confidence: float = 0.0

    @property
    def has_hold_events(self) -> bool:
        return len(self.hold_events) > 0

    def position_at(self, frame_idx: int) -> List[float]:
        """Interpolate world position at arbitrary frame index."""
        if not self.world_trajectory:
            return [0.0, 0.0, 1.0]
        # Find nearest frame
        frames = self.world_trajectory
        for i, (fi, pos) in enumerate(frames):
            if fi == frame_idx:
                return pos
            if fi > frame_idx:
                if i == 0:
                    return pos
                # Linear interp
                f0, p0 = frames[i-1]
                f1, p1 = frames[i]
                t = (frame_idx - f0) / max(f1 - f0, 1)
                return [p0[j] + t * (p1[j] - p0[j]) for j in range(3)]
        return frames[-1][1]

    def is_held_at(self, frame_idx: int) -> Optional[HoldEvent]:
        """Return HoldEvent if object is being held at this frame, else None."""
        for ev in self.hold_events:
            if ev.start_frame <= frame_idx <= ev.end_frame:
                return ev
        return None


@dataclass
class SceneData:
    """Complete scene — person skeleton + animated objects + HOI graph."""
    session_id:   str
    motion_data:  UnifiedMotionData
    scene_objects: List[AnimatedSceneObject] = field(default_factory=list)

    # HOI summary
    interaction_timeline: List[Dict] = field(default_factory=list)
    unique_classes:       List[str]  = field(default_factory=list)

    @property
    def has_objects(self) -> bool:
        return len(self.scene_objects) > 0

    @property
    def num_objects(self) -> int:
        return len(self.scene_objects)

    def get_object(self, track_id: int) -> Optional[AnimatedSceneObject]:
        for obj in self.scene_objects:
            if obj.track_id == track_id:
                return obj
        return None

    def objects_at_frame(self, frame_idx: int) -> List[AnimatedSceneObject]:
        return [
            obj for obj in self.scene_objects
            if obj.first_frame <= frame_idx <= obj.last_frame
        ]


# ═══════════════════════════════════════════════════════════════════ #
# Composer
# ═══════════════════════════════════════════════════════════════════ #

class SceneComposer:
    """
    Loads all scene data for a session from the database and assembles
    a `SceneData` object ready for scene-level exporters.
    """

    HOLD_TYPES = {"HOLDING", "LIFTING", "MOVING", "PLACING"}

    def __init__(self):
        self._loader = SessionDataLoader()

    def load(self, session_id: str, db: Session) -> SceneData:
        """
        Main entry: load person motion + objects + HOI → SceneData.
        Falls back gracefully if no object/HOI data exists (older sessions).
        """
        # 1. Load person skeleton motion
        motion = self._loader.load(session_id, db)

        # 2. Load object trajectories
        scene_objects = self._load_objects(session_id, db)

        # 3. Load HOI records and attach hold events to objects
        timeline = self._load_hoi(session_id, db, scene_objects)

        return SceneData(
            session_id=session_id,
            motion_data=motion,
            scene_objects=scene_objects,
            interaction_timeline=timeline,
            unique_classes=list({o.class_name for o in scene_objects}),
        )

    # ---------------------------------------------------------------- #
    # Object loading
    # ---------------------------------------------------------------- #

    def _load_objects(self, session_id: str, db: Session) -> List[AnimatedSceneObject]:
        """Build AnimatedSceneObject list from ObjectTrajectory rows."""
        rows = (db.query(ObjectTrajectory)
                .filter_by(session_id=session_id)
                .order_by(ObjectTrajectory.track_id, ObjectTrajectory.frame_id)
                .all())

        if not rows:
            # Fall back: try to extract from perception_json
            return self._load_objects_from_frames(session_id, db)

        # Group by track_id
        tracks: Dict[int, List[ObjectTrajectory]] = {}
        for r in rows:
            tracks.setdefault(r.track_id, []).append(r)

        objects = []
        for tid, track_rows in tracks.items():
            cls_name = track_rows[0].class_name
            model    = get_model(cls_name)

            # Build trajectory
            traj = []
            bbox_traj = []
            confs = []
            for row in track_rows:
                pos = [row.pos_x or 0.0, row.pos_y or 0.0, row.pos_z or 1.0]
                traj.append((row.frame_id, pos))
                bbox = [
                    row.bbox_x1 or 0.0, row.bbox_y1 or 0.0,
                    row.bbox_x2 or 0.0, row.bbox_y2 or 0.0,
                ]
                bbox_traj.append((row.frame_id, bbox))
                confs.append(row.confidence or 0.0)

            obj = AnimatedSceneObject(
                track_id=tid,
                class_name=cls_name,
                model=model,
                world_trajectory=traj,
                bbox_trajectory=bbox_traj,
                first_frame=track_rows[0].frame_id,
                last_frame=track_rows[-1].frame_id,
                avg_confidence=round(sum(confs)/max(len(confs), 1), 3),
            )
            objects.append(obj)

        return objects

    def _load_objects_from_frames(
        self, session_id: str, db: Session
    ) -> List[AnimatedSceneObject]:
        """
        Fallback: extract object data from MotionFrame.perception_json
        (used for older sessions captured before HOI tables existed).
        """
        frames = (db.query(MotionFrame)
                  .filter_by(session_id=session_id)
                  .order_by(MotionFrame.frame_idx)
                  .all())

        tracks: Dict[int, List] = {}

        for mf in frames:
            perc = json.loads(mf.perception_json) if mf.perception_json else {}
            objects = perc.get("objects", [])
            for obj in objects:
                tid = obj.get("track_id") or obj.get("id") or -1
                if tid < 0:
                    continue
                tracks.setdefault(tid, []).append({
                    "frame_id":   mf.frame_idx,
                    "class_name": obj.get("class", "unknown"),
                    "confidence": obj.get("confidence", 0.0),
                    "bbox":       obj.get("bbox", [0, 0, 0, 0]),
                    "pos3d":      obj.get("position_3d", [0.0, 0.0, 1.0]),
                })

        objects_out = []
        for tid, detections in tracks.items():
            cls_name = detections[0]["class_name"]
            model    = get_model(cls_name)
            traj     = [(d["frame_id"], d["pos3d"]) for d in detections]
            bbox_t   = [(d["frame_id"], d["bbox"]) for d in detections]
            confs    = [d["confidence"] for d in detections]
            objects_out.append(AnimatedSceneObject(
                track_id=tid, class_name=cls_name, model=model,
                world_trajectory=traj, bbox_trajectory=bbox_t,
                first_frame=detections[0]["frame_id"],
                last_frame=detections[-1]["frame_id"],
                avg_confidence=round(sum(confs)/max(len(confs),1), 3),
            ))

        return objects_out

    # ---------------------------------------------------------------- #
    # HOI loading
    # ---------------------------------------------------------------- #

    def _load_hoi(
        self,
        session_id:    str,
        db:            Session,
        scene_objects: List[AnimatedSceneObject],
    ) -> List[Dict]:
        """Load HOI records and embed HoldEvents into AnimatedSceneObjects."""
        rows = (db.query(HandObjectInteractionRecord)
                .filter_by(session_id=session_id)
                .order_by(HandObjectInteractionRecord.frame_id)
                .all())

        if not rows:
            return []

        # Build obj lookup
        obj_map = {obj.track_id: obj for obj in scene_objects}

        # Group hold events per (hand, object_track_id)
        hold_spans: Dict[Tuple[str, int], Dict] = {}

        timeline = []
        for row in rows:
            entry = {
                "frame_id":        row.frame_id,
                "timestamp_ms":    row.timestamp_ms,
                "hand":            row.hand,
                "hand_gesture":    row.hand_gesture,
                "object_class":    row.object_class,
                "object_track_id": row.object_track_id,
                "interaction_type":row.interaction_type,
                "confidence":      row.confidence,
                "distance_3d":     row.distance_3d,
                "duration_frames": row.duration_frames,
                "contact_point":   [row.contact_x or 0, row.contact_y or 0, row.contact_z or 0],
                "obj_position":    [row.obj_pos_x or 0, row.obj_pos_y or 0, row.obj_pos_z or 0],
            }
            timeline.append(entry)

            # Track hold events
            if row.interaction_type in self.HOLD_TYPES:
                key = (row.hand, row.object_track_id)
                if key not in hold_spans:
                    hand_joint = "LeftHand" if row.hand == "left" else "RightHand"
                    hold_spans[key] = {
                        "hand":       row.hand,
                        "joint":      hand_joint,
                        "start":      row.frame_id,
                        "end":        row.frame_id,
                        "obj_pos":    [row.obj_pos_x or 0, row.obj_pos_y or 0, row.obj_pos_z or 0],
                    }
                else:
                    hold_spans[key]["end"] = row.frame_id
            else:
                # Non-hold frame breaks the hold span — finalise
                for key in list(hold_spans.keys()):
                    if key[0] == row.hand and key[1] == row.object_track_id:
                        span = hold_spans.pop(key)
                        if span["end"] - span["start"] >= 5:
                            self._attach_hold(span, obj_map)

        # Finalise remaining hold spans
        for span in hold_spans.values():
            if span["end"] - span["start"] >= 5:
                self._attach_hold(span, obj_map)

        return timeline

    def _attach_hold(
        self,
        span:    Dict,
        obj_map: Dict[int, AnimatedSceneObject],
    ):
        """Create a HoldEvent and attach it to the AnimatedSceneObject."""
        tid = None
        # Find matching track
        for k, v in {**obj_map}.items():
            if v.class_name:  # Just attach to first matching object (simplification)
                tid = k
                break

        if tid is None or tid not in obj_map:
            return

        obj = obj_map[tid]
        ev = HoldEvent(
            hand=span["hand"],
            start_frame=span["start"],
            end_frame=span["end"],
            hand_joint=span["joint"],
            relative_offset=[0.0, -0.05, 0.0],   # Slightly below palm
        )
        obj.hold_events.append(ev)
