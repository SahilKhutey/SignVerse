import mediapipe as mp
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import threading


@dataclass
class Landmark:
    """Single landmark with x, y, z, visibility."""
    x: float
    y: float
    z: float
    v: float = 1.0  # visibility/presence confidence


@dataclass
class PerceptionResult:
    """Full perception output for one frame."""
    pose: List[Landmark] = field(default_factory=list)         # 33 points
    left_hand: List[Landmark] = field(default_factory=list)    # 21 points
    right_hand: List[Landmark] = field(default_factory=list)   # 21 points
    face: List[Landmark] = field(default_factory=list)         # 478 points (sampled to 100)
    objects: List[Dict] = field(default_factory=list)          # from YOLO
    confidence_mean: float = 0.0
    timestamp_ms: int = 0
    frame_id: int = 0
    gestures: Dict = field(default_factory=dict)
    expression: Dict = field(default_factory=dict)
    interaction: Dict = field(default_factory=dict)
    primitives: List[Dict] = field(default_factory=list)
    intent: str = "IDLE"
    
    def to_dict(self) -> Dict:
        return {
            "pose": [asdict(l) for l in self.pose],
            "left_hand": [asdict(l) for l in self.left_hand],
            "right_hand": [asdict(l) for l in self.right_hand],
            "face": [asdict(l) for l in self.face],
            "objects": self.objects,
            "confidence_mean": self.confidence_mean,
            "timestamp_ms": self.timestamp_ms,
            "frame_id": self.frame_id,
            "gestures": self.gestures,
            "expression": self.expression,
            "interaction": self.interaction,
            "primitives": self.primitives,
            "intent": self.intent,
        }


class HolisticExtractor:
    """Thread-safe MediaPipe Holistic wrapper."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Singleton initialization."""
        self.mp_holistic = mp.solutions.holistic
        self.holistic = self.mp_holistic.Holistic(
            static_image_mode=False,
            model_complexity=1,           # 0=lite, 1=full, 2=heavy
            smooth_landmarks=True,
            enable_segmentation=False,
            refine_face_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        from .hand_gestures import HandGestureClassifier
        from .expressions import ExpressionAnalyzer
        self.gesture_classifier = HandGestureClassifier()
        self.expression_analyzer = ExpressionAnalyzer()
    
    def extract(self, frame_rgb: np.ndarray, frame_id: int = 0, timestamp_ms: int = 0) -> PerceptionResult:
        """
        Run holistic on RGB frame.
        Returns PerceptionResult with all landmark sets.
        """
        if frame_rgb is None or frame_rgb.size == 0:
            return PerceptionResult(frame_id=frame_id, timestamp_ms=timestamp_ms)

        # Ensure correct format
        if frame_rgb.dtype != np.uint8:
            frame_rgb = (frame_rgb * 255).astype(np.uint8)
        
        # Process
        results = self.holistic.process(frame_rgb)
        
        # Extract landmarks
        pose_lms = self._extract_landmarks(results.pose_landmarks)
        left_lms = self._extract_landmarks(results.left_hand_landmarks)
        right_lms = self._extract_landmarks(results.right_hand_landmarks)
        face_lms = self._extract_landmarks(results.face_landmarks, sample_count=100)
        
        # Classify hand gestures
        gestures = self.gesture_classifier.classify_both_hands(left_lms, right_lms)
        
        # Classify expressions from full face mesh landmarks
        full_face_lms = self._extract_landmarks(results.face_landmarks)
        expression_data = self.expression_analyzer.analyze(full_face_lms)
        
        # Compute mean confidence
        all_vis = [l.v for l in pose_lms + left_lms + right_lms if l.v > 0]
        conf = float(np.mean(all_vis)) if all_vis else 0.0
        
        return PerceptionResult(
            pose=pose_lms,
            left_hand=left_lms,
            right_hand=right_lms,
            face=face_lms,
            confidence_mean=conf,
            frame_id=frame_id,
            timestamp_ms=timestamp_ms,
            gestures=gestures,
            expression=expression_data,
        )
    
    def close(self):
        """Close MediaPipe Holistic resources."""
        if hasattr(self, "holistic") and self.holistic:
            self.holistic.close()
    
    @staticmethod
    def _extract_landmarks(mp_landmarks, sample_count: Optional[int] = None) -> List[Landmark]:
        """Convert MediaPipe landmarks to our schema."""
        if mp_landmarks is None:
            return []
        
        landmarks = [
            Landmark(
                x=lm.x, y=lm.y, z=lm.z,
                v=getattr(lm, 'visibility', 1.0) or 1.0
            )
            for lm in mp_landmarks.landmark
        ]
        
        if sample_count and len(landmarks) > sample_count:
            # Subsample evenly (e.g., face 478 → 100)
            indices = np.linspace(0, len(landmarks) - 1, sample_count, dtype=int)
            landmarks = [landmarks[i] for i in indices]
        
        return landmarks
