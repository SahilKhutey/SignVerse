import cv2
import numpy as np
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, AsyncGenerator
import json

from .pose_extractor import PoseExtractor
from .kalman_smoother import TemporalSmoother
from .schemas import PoseFrame, SessionMetadata, Landmark
from backend.config import settings

class FrameProcessor:
    """Manages full computer vision tracking session, ingestion pipeline, and export logic"""

    def __init__(self, source: str, filename: str):
        self.session_id = str(uuid.uuid4())[:12]
        self.source = source
        self.filename = filename
        self.frames: List[PoseFrame] = []
        self.smoother = TemporalSmoother()
        self.extractor = PoseExtractor()
        self.metadata: Optional[SessionMetadata] = None

    def process_video(self, video_path: str, max_frames: Optional[int] = None) -> SessionMetadata:
        """Extract skeletal landmarks from an offline video file frame-by-frame"""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file path: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or settings.target_fps
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        max_frames = max_frames or min(total, settings.max_frames_per_session)

        self.frames = []
        frame_id = 0

        while cap.isOpened() and frame_id < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            timestamp = frame_id / fps
            pose = self.extractor.extract(frame, frame_id, timestamp)
            self.frames.append(pose)
            frame_id += 1

        cap.release()

        # Apply post-hoc temporal Kalman filter smoothing if enabled
        if settings.enable_smoothing:
            for i, pf in enumerate(self.frames):
                d = {
                    "pose_33": [lm.model_dump() for lm in pf.pose_33],
                    "left_hand_21": [lm.model_dump() for lm in pf.left_hand_21],
                    "right_hand_21": [lm.model_dump() for lm in pf.right_hand_21],
                    "face_468": [lm.model_dump() for lm in pf.face_468],
                }
                smoothed = self.smoother.smooth_frame(d)
                self.frames[i] = PoseFrame(
                    frame_id=pf.frame_id,
                    timestamp=pf.timestamp,
                    pose_33=[Landmark(**x) for x in smoothed["pose_33"]] if smoothed["pose_33"] else [],
                    left_hand_21=[Landmark(**x) for x in smoothed["left_hand_21"]] if smoothed["left_hand_21"] else [],
                    right_hand_21=[Landmark(**x) for x in smoothed["right_hand_21"]] if smoothed["right_hand_21"] else [],
                    face_468=[Landmark(**x) for x in smoothed["face_468"]] if smoothed["face_468"] else [],
                    confidence=pf.confidence,
                )

        self.metadata = SessionMetadata(
            session_id=self.session_id,
            source=self.source,
            filename=self.filename,
            fps=fps,
            frame_count=len(self.frames),
            duration_sec=len(self.frames) / fps,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status="ready",
        )
        return self.metadata

    async def stream_camera(self, camera_id: int = 0, duration_sec: int = 30) -> AsyncGenerator[PoseFrame, None]:
        """Captures webcam stream frames in real-time, executing inference and streaming coordinates"""
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            raise ValueError(f"Cannot initialize camera device index: {camera_id}")

        fps = cap.get(cv2.CAP_PROP_FPS) or settings.target_fps
        start = cv2.getTickCount()
        frame_id = 0
        self.smoother.reset()

        while True:
            elapsed = (cv2.getTickCount() - start) / cv2.getTickFrequency()
            if elapsed >= duration_sec:
                break
            ret, frame = cap.read()
            if not ret:
                break
            timestamp = elapsed
            pose = self.extractor.extract(frame, frame_id, timestamp)

            # Online Real-time Kalman smoothing
            d = {
                "pose_33": [lm.model_dump() for lm in pose.pose_33],
                "left_hand_21": [lm.model_dump() for lm in pose.left_hand_21],
                "right_hand_21": [lm.model_dump() for lm in pose.right_hand_21],
                "face_468": [lm.model_dump() for lm in pose.face_468],
            }
            smoothed = self.smoother.smooth_frame(d)
            pose.pose_33 = [Landmark(**x) for x in smoothed["pose_33"]] if smoothed["pose_33"] else []
            pose.left_hand_21 = [Landmark(**x) for x in smoothed["left_hand_21"]] if smoothed["left_hand_21"] else []
            pose.right_hand_21 = [Landmark(**x) for x in smoothed["right_hand_21"]] if smoothed["right_hand_21"] else []
            pose.face_468 = [Landmark(**x) for x in smoothed["face_468"]] if smoothed["face_468"] else []

            self.frames.append(pose)
            yield pose
            frame_id += 1

        cap.release()
        self.metadata = SessionMetadata(
            session_id=self.session_id,
            source="camera",
            filename=f"camera_{camera_id}",
            fps=fps,
            frame_count=len(self.frames),
            duration_sec=elapsed,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status="ready",
        )

    def to_json(self) -> str:
        """Export session metadata and all frames to JSON format"""
        return json.dumps(
            {
                "metadata": self.metadata.model_dump(mode="json") if self.metadata else {},
                "frames": [f.model_dump() for f in self.frames],
            },
            indent=2,
        )
