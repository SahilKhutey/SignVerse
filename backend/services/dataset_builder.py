import json
import cv2
import numpy as np
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
from sqlalchemy.orm import Session

from ..models.database import MotionSession, MotionFrame
from .perception_pipeline import PerceptionPipeline
from .kinematics.bone_vectors import compute_bone_vectors
from .kinematics.euler_angles import bone_to_euler, euler_to_quat
from .motion_intelligence.action_segmenter import segment_actions

DATASETS_DIR = Path("datasets")
THUMB_DIR = DATASETS_DIR / "thumbnails"
THUMB_DIR.mkdir(parents=True, exist_ok=True)

# Bone parent map for kinematic chain
_BONE_PARENTS = {
    "spine": "root", "chest": "spine", "neck": "chest",
    "l_shoulder": "chest", "l_elbow": "l_shoulder", "l_wrist": "l_elbow",
    "r_shoulder": "chest", "r_elbow": "r_shoulder", "r_wrist": "r_elbow",
    "l_hip": "root", "l_knee": "l_hip", "l_ankle": "l_knee",
    "r_hip": "root", "r_knee": "r_hip", "r_ankle": "r_knee",
}

class DatasetBuilder:
    """
    Orchestrates the full dataset creation pipeline.
    Takes raw frames → produces fully-labeled session in SQLite.
    """

    def __init__(self, db: Session):
        self.db = db
        self.pipeline = PerceptionPipeline()

    def build_session(
        self,
        job_id: str,
        frames: list,
        fps: float,
        source_type: str,
        name: str = None
    ) -> str:
        """
        Build a complete session from raw frames.

        Args:
            job_id: tracking ID from input layer
            frames: list of BGR float32 frames (any size)
            fps: frames per second
            source_type: 'webcam' | 'upload' | 'youtube' | 'demo'
            name: optional human-readable name

        Returns:
            session_id (UUID string)
        """
        session_id = str(uuid4())
        name = name or f"{source_type}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"

        # 1. Create session row
        session = MotionSession(
            id=session_id,
            name=name,
            source_type=source_type,
            fps=fps,
            frame_count=len(frames),
            duration_s=round(len(frames) / fps, 2),
            action_label="unlabeled",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(session)

        # 2. Process each frame
        kin_frames = []
        confidences = []
        prev_vecs = {}
        last_result = None

        for idx, frame in enumerate(frames):
            # Run perception
            result = self.pipeline.process_frame(frame)
            if result is None or not result.pose:
                continue

            ts_ms = round((idx / fps) * 1000, 2)

            # 3. Compute kinematics
            bone_vecs = compute_bone_vectors(result.pose, prev_vecs)
            prev_vecs = bone_vecs
            kin = self._build_kinematics(bone_vecs, idx, ts_ms)
            kin_frames.append(kin)

            # 4. Per-frame confidence
            conf = float(np.mean([
                (l.v if hasattr(l, 'v') else l.get('v', 1.0))
                for l in result.pose if l is not None
            ]))
            confidences.append(conf)
            last_result = result

            # 5. Persist frame row
            mf = MotionFrame(
                id=str(uuid4()),
                session_id=session_id,
                frame_idx=idx,
                timestamp_ms=ts_ms,
                perception_json=json.dumps(result.to_dict()),
                kinematics_json=json.dumps(kin),
                confidence_mean=round(conf, 4),
            )
            self.db.add(mf)

        # 6. Generate thumbnail
        thumb_path = self._make_thumbnail(frames, session_id, last_result)

        # 7. Run action segmentation
        segments = segment_actions(kin_frames, fps)
        top_action = self._dominant_action(segments)

        # 8. Update session metadata
        session.thumbnail_path = str(thumb_path)
        session.avg_confidence = round(float(np.mean(confidences)), 4) if confidences else 0.0
        session.action_label = top_action

        self.db.commit()
        return session_id

    def build_session_from_video(
        self,
        job_id: str,
        video_path: str,
        source_type: str,
        name: str = None,
        progress_callback = None,
        check_cancelled = None
    ) -> str:
        """
        Build a complete session from a video file directly, reading frame-by-frame to save memory.
        """
        import asyncio
        session_id = str(uuid4())
        name = name or f"{source_type}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}"

        # 1. Open video
        video_path_str = str(video_path)
        cap = cv2.VideoCapture(video_path_str)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file {video_path}")
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        
        # 2. Create session row
        session = MotionSession(
            id=session_id,
            name=name,
            source_type=source_type,
            fps=fps,
            frame_count=total_frames,
            duration_s=round(total_frames / fps, 2),
            action_label="unlabeled",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.db.add(session)

        # 3. Process frame-by-frame
        kin_frames = []
        confidences = []
        prev_vecs = {}
        last_result = None
        thumbnail_frame = None
        thumb_idx = max(0, total_frames // 4)

        for idx in range(total_frames):
            # Check cancellation
            if check_cancelled and check_cancelled():
                cap.release()
                raise asyncio.CancelledError()

            ret, frame = cap.read()
            if not ret:
                break

            # Save frame for thumbnail at 25% progress
            if idx == thumb_idx:
                thumbnail_frame = frame.copy()

            # Run perception pipeline (convert BGR frame to float32 normalized)
            frame_normalized = frame.astype(float) / 255.0
            result = self.pipeline.process_frame(frame_normalized)
            if result is None or not result.pose:
                continue

            ts_ms = round((idx / fps) * 1000, 2)

            # Compute kinematics
            bone_vecs = compute_bone_vectors(result.pose, prev_vecs)
            prev_vecs = bone_vecs
            kin = self._build_kinematics(bone_vecs, idx, ts_ms)
            kin_frames.append(kin)

            # Per-frame confidence
            conf = float(np.mean([
                (l.v if hasattr(l, 'v') else l.get('v', 1.0))
                for l in result.pose if l is not None
            ]))
            confidences.append(conf)
            last_result = result

            # Persist frame row
            mf = MotionFrame(
                id=str(uuid4()),
                session_id=session_id,
                frame_idx=idx,
                timestamp_ms=ts_ms,
                perception_json=json.dumps(result.to_dict()),
                kinematics_json=json.dumps(kin),
                confidence_mean=round(conf, 4),
            )
            self.db.add(mf)

            # Report progress
            if progress_callback:
                progress_callback((idx + 1) / total_frames)

        cap.release()

        # 4. Generate thumbnail
        thumb_path = ""
        if thumbnail_frame is not None:
            if last_result and last_result.pose:
                from .perception.overlay import draw_pose_overlay as draw_overlay
                thumbnail_frame = draw_overlay(thumbnail_frame, last_result)
            thumb_path = THUMB_DIR / f"{session_id}.jpg"
            cv2.imwrite(str(thumb_path), thumbnail_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # 5. Run action segmentation
        segments = segment_actions(kin_frames, fps)
        top_action = self._dominant_action(segments)

        # 6. Update session metadata
        session.thumbnail_path = str(thumb_path)
        session.avg_confidence = round(float(np.mean(confidences)), 4) if confidences else 0.0
        session.action_label = top_action

        self.db.commit()
        return session_id


    def _build_kinematics(self, bone_vecs, idx, ts_ms):
        """Build the kinematics JSON blob for one frame."""
        euler_deg, euler_rad, quats, vels, accs = {}, {}, {}, {}, {}

        for bone, bv in bone_vecs.items():
            parent = bone_vecs.get(_BONE_PARENTS.get(bone))
            e_rad, e_deg = bone_to_euler(
                bv['dir'],
                parent['dir'] if parent else None
            )
            euler_deg[bone] = [round(x, 4) for x in e_deg]
            euler_rad[bone] = [round(x, 6) for x in e_rad]
            quats[bone] = [round(x, 6) for x in euler_to_quat(e_rad)]
            vels[bone] = [round(x, 6) for x in bv.get('vel', [0, 0, 0])]

        return {
            "frame_idx": idx,
            "timestamp_ms": ts_ms,
            "bone_vectors": {
                b: {
                    "dir": [round(x, 4) for x in v['dir']],
                    "len": round(v['len'], 4),
                    "vel": [round(x, 6) for x in v.get('vel', [0, 0, 0])],
                }
                for b, v in bone_vecs.items()
            },
            "euler_deg": euler_deg,
            "euler_rad": euler_rad,
            "quaternions": quats,
            "velocities": vels,
        }

    def _make_thumbnail(self, frames, sid, last_result):
        """Generate a thumbnail from the 25% frame with overlay."""
        if not frames:
            return ""
        idx = max(0, len(frames) // 4)
        
        # Ensure we have a uint8 copy for overlay drawing
        frame = frames[idx]
        if frame.dtype != np.uint8:
            frame_u8 = (frame * 255).astype(np.uint8)
        else:
            frame_u8 = frame.copy()

        if last_result and last_result.pose:
            from .perception.overlay import draw_pose_overlay as draw_overlay
            frame_u8 = draw_overlay(frame_u8, last_result)

        path = THUMB_DIR / f"{sid}.jpg"
        cv2.imwrite(str(path), frame_u8, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path

    def _dominant_action(self, segments):
        """Return the most common action label from segments."""
        if not segments:
            return "IDLE"
        counts = Counter(s['action'] for s in segments)
        return counts.most_common(1)[0][0]
