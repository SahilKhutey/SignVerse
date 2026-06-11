import time
import numpy as np
import cv2
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from backend.services.perception.holistic_extractor import HolisticExtractor, PerceptionResult, Landmark
from backend.services.perception.object_detector import ObjectDetector3D
# Backward-compatibility alias (perception_pipeline expects the old name)
ObjectDetector = ObjectDetector3D

from backend.services.motion_fusion.kalman_smoother import TemporalSmoother
from backend.services.normalizer import normalize_frame
from backend.core.schemas import SessionMetadata, PoseFrame
from backend.config import settings

from backend.services.perception.interaction import InteractionEngine
from backend.services.motion_intelligence.action_primitives import ActionPrimitiveDetector
from backend.services.motion_intelligence.intent_classifier import IntentClassifier


class PerceptionPipeline:
    """Orchestrates all perception extractors + smoothing + semantic tracking layers."""
    
    def __init__(self):
        self.holistic = HolisticExtractor()
        self.detector = ObjectDetector()
        self.smoother = TemporalSmoother()
        
        self.interaction_engine = InteractionEngine()
        self.primitive_detector = ActionPrimitiveDetector()
        self.intent_classifier = IntentClassifier()
        
        self.last_interaction_graph = None
        self.last_primitives_data = None
        
        # Performance tracking
        self.last_timing = None
        self.avg_latency_ms = 0
    
    def process_frame(
        self, 
        frame: np.ndarray, 
        frame_id: int = 0, 
        timestamp_ms: int = 0
    ) -> PerceptionResult:
        """
        Process one frame through full perception stack.
        Returns unified PerceptionResult.
        """
        start = time.time()
        
        # Normalize
        normalized = normalize_frame(frame, 640, 480)
        
        # Holistic (RGB float32 [0,1] input)
        rgb_uint8 = (normalized * 255).astype(np.uint8)
        result = self.holistic.extract(rgb_uint8, frame_id, timestamp_ms)
        
        # YOLO (BGR uint8 input)
        bgr = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR) if len(rgb_uint8.shape) == 3 else rgb_uint8
        result.objects = self.detector.detect(bgr, persist=True)
        
        # Smooth
        result = self.smoother.smooth(result)
        
        # 1. Spatial interaction analysis
        interaction_graph = self.interaction_engine.analyze_frame(
            body_landmarks=[{"x": l.x, "y": l.y, "z": l.z} for l in result.pose],
            left_hand=[{"x": l.x, "y": l.y, "z": l.z} for l in result.left_hand] if result.left_hand else None,
            right_hand=[{"x": l.x, "y": l.y, "z": l.z} for l in result.right_hand] if result.right_hand else None,
            left_gesture=result.gestures.get("left_hand"),
            right_gesture=result.gestures.get("right_hand"),
            objects=result.objects,
            gaze=result.expression.get("gaze", {"direction": "center"}),
            prev_interactions=self.last_interaction_graph
        )
        self.last_interaction_graph = interaction_graph
        result.interaction = self.interaction_engine.to_dict(interaction_graph)
        
        # 2. Temporal Action Primitives detection
        primitives_data = self.primitive_detector.detect(
            result.interaction,
            self.last_primitives_data
        )
        self.last_primitives_data = primitives_data
        result.primitives = primitives_data.get("primitives", [])
        
        # 3. Contextual Intent Classification
        result.intent = self.intent_classifier.classify(
            result.interaction,
            result.primitives
        )
        
        # Track timing
        elapsed_ms = (time.time() - start) * 1000
        self.avg_latency_ms = 0.9 * self.avg_latency_ms + 0.1 * elapsed_ms
        
        return result
    
    def process_frame_from_jpeg(self, jpeg_bytes: bytes) -> PerceptionResult:
        """Process frame from JPEG bytes (WebSocket path)."""
        np_arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return self.process_frame(frame)

    def process_video(self, video_path: str, source: str, filename: str, max_frames: Optional[int] = None) -> dict:
        """Process an offline video file and return metadata and frame coordinates."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video file: {video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS) or settings.target_fps
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        max_frames = max_frames or min(total, settings.max_frames_per_session)
        
        session_id = str(uuid.uuid4())[:12]
        frames = []
        frame_id = 0
        self.smoother.reset()
        self.last_interaction_graph = None
        self.last_primitives_data = None
        
        while cap.isOpened() and frame_id < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            timestamp = frame_id / fps
            
            # Process frame through the holistic + YOLO pipeline
            res = self.process_frame(frame, frame_id, int(timestamp * 1000))
            
            # Map back to PoseFrame schema
            pose_frame = PoseFrame(
                frame_id=frame_id,
                timestamp=timestamp,
                pose_33=[Landmark(x=lm.x, y=lm.y, z=lm.z, v=lm.v) for lm in res.pose],
                left_hand_21=[Landmark(x=lm.x, y=lm.y, z=lm.z, v=lm.v) for lm in res.left_hand],
                right_hand_21=[Landmark(x=lm.x, y=lm.y, z=lm.z, v=lm.v) for lm in res.right_hand],
                face_468=[Landmark(x=lm.x, y=lm.y, z=lm.z, v=lm.v) for lm in res.face],
                confidence=res.confidence_mean
            )
            frames.append(pose_frame)
            frame_id += 1
            
        cap.release()
        
        metadata = SessionMetadata(
            session_id=session_id,
            source=source,
            filename=filename,
            fps=fps,
            frame_count=len(frames),
            duration_sec=len(frames) / fps,
            created_at=datetime.utcnow(),
            status="ready"
        )
        
        return {
            "session_id": session_id,
            "metadata": metadata,
            "frames": frames
        }
