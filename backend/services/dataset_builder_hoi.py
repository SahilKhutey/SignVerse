"""
DatasetBuilderHOI — extends DatasetBuilder to capture:
  • Object trajectories (3D position per frame) via ObjectDetector3D
  • Hand-Object Interaction records (HOI) via upgraded InteractionEngine
  • Enhanced perception_json with objects_3d embedded

Backward-compatible: original DatasetBuilder is imported and used as base.
New HOI tables are populated additionally.
"""
import json
import numpy as np
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from collections import Counter
from sqlalchemy.orm import Session
from typing import List, Dict, Optional

from backend.models.database import (
    MotionSession, MotionFrame,
    ObjectTrajectory, HandObjectInteractionRecord,
)
from backend.services.dataset_builder import DatasetBuilder
from backend.services.perception_pipeline import PerceptionPipeline
from backend.services.kinematics.bone_vectors import compute_bone_vectors
from backend.services.kinematics.euler_angles import bone_to_euler, euler_to_quat
from backend.services.motion_intelligence.action_segmenter import segment_actions

DATASETS_DIR = Path("datasets")
THUMB_DIR = DATASETS_DIR / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

_BONE_PARENTS = {
    "spine": "root", "chest": "spine", "neck": "chest",
    "l_shoulder": "chest", "l_elbow": "l_shoulder", "l_wrist": "l_elbow",
    "r_shoulder": "chest", "r_elbow": "r_shoulder", "r_wrist": "r_elbow",
    "l_hip": "root", "l_knee": "l_hip", "l_ankle": "l_knee",
    "r_hip": "root", "r_knee": "r_hip", "r_ankle": "r_knee",
}

# Interaction types that count as "hold"
_HOLD_TYPES = {"HOLDING", "LIFTING", "MOVING", "PLACING", "GRASPING"}


class DatasetBuilderHOI(DatasetBuilder):
    """
    Enhanced dataset builder.
    All original functionality is preserved. Additionally:
      - Saves ObjectTrajectory rows (one per object per frame)
      - Saves HandObjectInteractionRecord rows
      - Updates MotionFrame.perception_json with objects_3d list
      - Updates MotionSession with object metadata
    """
    def __init__(self, db: Session):
        super().__init__(db)
        from backend.services.depth.metric_reconstruction import MetricReconstructor
        self.reconstructor = MetricReconstructor(enable_depth_model=True)

    def build_session(
        self,
        job_id:      str,
        frames:      List[np.ndarray],
        fps:         float,
        source_type: str,
        name:        str = None,
    ) -> str:
        """
        Full pipeline: person + objects + HOI → SQLite.
        Returns session_id.
        """
        session_id = str(uuid4())
        name = name or f"{source_type}_{datetime.utcnow():%Y%m%d_%H%M%S}"

        session = MotionSession(
            id=session_id,
            name=name,
            source_type=source_type,
            fps=fps,
            frame_count=len(frames),
            duration_s=round(len(frames) / fps, 2),
            action_label="unlabeled",
            created_at=datetime.utcnow(),
        )
        self.db.add(session)

        kin_frames      = []
        confidences     = []
        prev_vecs       = {}
        last_result     = None
        prev_interaction= None

        # Track object + HOI accumulation for bulk inserts
        obj_rows: List[ObjectTrajectory] = []
        hoi_rows: List[HandObjectInteractionRecord] = []

        # For session-level metadata
        all_classes:     Counter = Counter()
        total_objects    = 0
        total_hoi        = 0

        # Scale recovery aggregators
        scale_factors = []
        person_heights = []

        for idx, frame in enumerate(frames):
            result = self.pipeline.process_frame(frame)
            if result is None or not result.pose:
                continue

            ts_ms = round((idx / fps) * 1000, 2)

            # ── Kinematics ──────────────────────────────────────────
            bone_vecs = compute_bone_vectors(result.pose, prev_vecs)
            prev_vecs = bone_vecs
            kin = self._build_kinematics(bone_vecs, idx, ts_ms)
            kin_frames.append(kin)

            conf = float(np.mean([
                (l.v if hasattr(l, "v") else l.get("v", 1.0))
                for l in result.pose if l is not None
            ]))
            confidences.append(conf)
            last_result = result

            # ── Objects (from upgraded detector via pipeline) ────────
            objects = result.objects   # Now includes position_3d, depth_m, velocity_3d

            for obj in objects:
                all_classes[obj.get("class", "unknown")] += 1
                total_objects += 1
                pos3d = obj.get("position_3d", [0.0, 0.0, 1.0])
                vel3d = obj.get("velocity_3d", [0.0, 0.0, 0.0])
                bbox  = obj.get("bbox", [0, 0, 0, 0])

                obj_rows.append(ObjectTrajectory(
                    session_id  = session_id,
                    frame_id    = idx,
                    timestamp_ms= ts_ms,
                    track_id    = obj.get("track_id") or -1,
                    class_name  = obj.get("class", "unknown"),
                    class_id    = obj.get("class_id"),
                    confidence  = obj.get("confidence"),
                    bbox_x1=bbox[0], bbox_y1=bbox[1], bbox_x2=bbox[2], bbox_y2=bbox[3],
                    pos_x=pos3d[0], pos_y=pos3d[1], pos_z=pos3d[2],
                    depth_m=obj.get("depth_m"),
                    vel_x=vel3d[0], vel_y=vel3d[1], vel_z=vel3d[2],
                    age_frames=obj.get("age_frames", 1),
                ))

            # ── HOI (from interaction graph) ─────────────────────────
            iactions = result.interaction.get("hand_object_interactions", [])
            for ia in iactions:
                total_hoi += 1
                contact = ia.get("contact_point_3d", [0, 0, 0])
                obj_pos = ia.get("object_position_3d", [0, 0, 0])
                hoi_rows.append(HandObjectInteractionRecord(
                    session_id       = session_id,
                    frame_id         = idx,
                    timestamp_ms     = ts_ms,
                    hand             = ia.get("hand"),
                    hand_gesture     = ia.get("hand_gesture"),
                    object_track_id  = ia.get("object_id"),
                    object_class     = ia.get("object_class"),
                    interaction_type = ia.get("interaction_type"),
                    confidence       = ia.get("confidence"),
                    distance_3d      = ia.get("distance_3d"),
                    distance_2d      = ia.get("distance_px"),
                    duration_frames  = ia.get("duration_frames", 1),
                    contact_x=contact[0], contact_y=contact[1], contact_z=contact[2],
                    obj_pos_x=obj_pos[0], obj_pos_y=obj_pos[1], obj_pos_z=obj_pos[2],
                    first_frame=ia.get("first_frame", idx),
                    last_frame=ia.get("last_frame", idx),
                ))

            # ── Metric Depth 3D Reconstruction ───────────────────────
            metric_frame = None
            try:
                def to_dict_list(landmarks):
                    return [{"x": float(l.x), "y": float(l.y), "z": float(l.z), "v": float(l.v if hasattr(l, "v") else getattr(l, "visibility", 1.0))} for l in landmarks if l is not None]

                pose_dict_list = to_dict_list(result.pose)
                left_hand_dict_list = to_dict_list(result.left_hand)
                right_hand_dict_list = to_dict_list(result.right_hand)

                metric_frame = self.reconstructor.reconstruct_frame(
                    frame=frame,
                    perception={
                        "pose_33": pose_dict_list,
                        "left_hand_21": left_hand_dict_list,
                        "right_hand_21": right_hand_dict_list,
                        "objects": objects
                    },
                    frame_id=idx,
                    timestamp_ms=ts_ms
                )
                if metric_frame:
                    if metric_frame.scale_factor:
                        scale_factors.append(metric_frame.scale_factor)
                    if metric_frame.person_height_m:
                        person_heights.append(metric_frame.person_height_m)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error("Failed to run metric reconstruction in builder: %s", e)

            # ── Build enhanced perception JSON ───────────────────────
            perc_dict = result.to_dict()
            # Patch objects with 3D data (in case pipeline doesn't embed it)
            perc_dict["objects"] = objects
            perc_dict["objects_3d"] = [
                {
                    "class":       o.get("class"),
                    "track_id":    o.get("track_id"),
                    "position_3d": o.get("position_3d", [0, 0, 1]),
                    "depth_m":     o.get("depth_m", 1.0),
                    "bbox":        o.get("bbox", [0, 0, 0, 0]),
                    "velocity_3d": o.get("velocity_3d", [0, 0, 0]),
                }
                for o in objects
            ]
            perc_dict["interaction_graph"] = result.interaction

            # ── Persist MotionFrame ──────────────────────────────────
            mf = MotionFrame(
                id              = str(uuid4()),
                session_id      = session_id,
                frame_idx       = idx,
                timestamp_ms    = ts_ms,
                perception_json = json.dumps(perc_dict),
                kinematics_json = json.dumps(kin),
                confidence_mean = round(conf, 4),
                metric_json     = json.dumps(metric_frame.to_json_dict()) if metric_frame else None,
                scale_factor    = metric_frame.scale_factor if metric_frame else None,
                depth_confidence= metric_frame.depth_confidence if metric_frame else None,
            )
            self.db.add(mf)

        # ── Bulk-insert object + HOI rows ────────────────────────────
        if obj_rows:
            self.db.bulk_save_objects(obj_rows)
        if hoi_rows:
            self.db.bulk_save_objects(hoi_rows)

        # ── Thumbnail ────────────────────────────────────────────────
        thumb_path = self._make_thumbnail(frames, session_id, last_result)

        # ── Action segmentation ──────────────────────────────────────
        segments  = segment_actions(kin_frames, fps)
        top_action = self._dominant_action(segments)

        # ── Primary interacted object ────────────────────────────────
        primary_obj = all_classes.most_common(1)[0][0] if all_classes else None
        unique_obj_list = list(all_classes.keys())

        # ── Update session row ───────────────────────────────────────
        import json as _json
        session.thumbnail_path   = str(thumb_path)
        session.avg_confidence   = round(float(np.mean(confidences)), 4) if confidences else 0.0
        session.action_label     = top_action
        session.object_count     = total_objects
        session.interaction_count= total_hoi
        session.primary_object   = primary_obj
        session.unique_objects   = _json.dumps(unique_obj_list)

        # Metric depth session metadata
        if scale_factors:
            session.scale_factor_mean = float(np.mean(scale_factors))
            session.scale_factor_std = float(np.std(scale_factors))
        if person_heights:
            session.person_height_m = float(np.mean(person_heights))
        session.camera_intrinsics_json = _json.dumps(self.reconstructor._current_intrinsics.to_dict()) if self.reconstructor._current_intrinsics else None
        session.depth_model_used = self.reconstructor.depth_model_name
        session.has_metric_data = len(scale_factors) > 0

        self.db.commit()
        return session_id
