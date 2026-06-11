import cv2
import numpy as np
import mediapipe as mp
import mediapipe.python.solutions.holistic as mp_holistic
import mediapipe.python.solutions.pose as mp_pose
import mediapipe.python.solutions.hands as mp_hands
from typing import List, Tuple, Optional
from .schemas import Landmark, PoseFrame
from backend.config import settings

class PoseExtractor:
    """
    Unified MediaPipe Holistic landmark extractor.
    Extracts: 33 body pose, 21 left hand, 21 right hand, and 468 facial mesh coordinates.
    """

    POSE_CONNECTIONS = mp_holistic.POSE_CONNECTIONS
    HAND_CONNECTIONS = mp_holistic.HAND_CONNECTIONS
    FACE_CONNECTIONS = mp_holistic.FACEMESH_CONTOURS

    def __init__(self):
        self.mp_holistic = mp_holistic
        self.holistic = self.mp_holistic.Holistic(
            static_image_mode=False,
            model_complexity=settings.mp_model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            refine_face_landmarks=False,
            min_detection_confidence=settings.mp_min_detection_confidence,
            min_tracking_confidence=settings.mp_min_tracking_confidence,
        )

    def extract(self, frame: np.ndarray, frame_id: int, timestamp: float) -> PoseFrame:
        """Process a single frame to extract holistic landmarks"""
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.holistic.process(rgb)

        pose = self._landmarks_to_list(results.pose_landmarks, w, h)
        lh = self._landmarks_to_list(results.left_hand_landmarks, w, h)
        rh = self._landmarks_to_list(results.right_hand_landmarks, w, h)

        # Sample face landmarks to 100 points for frontend rendering performance
        face_full = self._landmarks_to_list(results.face_landmarks, w, h)
        face = face_full[::max(1, len(face_full) // 100)] if face_full else []

        # Average confidence from pose visibility
        confidence = 0.0
        if pose:
            confidence = sum(p.get("v", 1.0) for p in pose) / len(pose)

        return PoseFrame(
            frame_id=frame_id,
            timestamp=timestamp,
            pose_33=[Landmark(**p) for p in pose],
            left_hand_21=[Landmark(**p) for p in lh],
            right_hand_21=[Landmark(**p) for p in rh],
            face_468=[Landmark(**p) for p in face],
            confidence=confidence,
        )

    def draw_overlay(self, frame: np.ndarray, pose_frame: PoseFrame) -> np.ndarray:
        """Renders 2D skeletal line overlays and info HUD onto BGR frame"""
        annotated = frame.copy()
        h, w = frame.shape[:2]

        # Draw Pose Connections
        if pose_frame.pose_33:
            landmarks = self._to_mediapipe_normalized(pose_frame.pose_33, w, h)
            annotated = self._draw_connections(
                annotated, landmarks, self.POSE_CONNECTIONS, (255, 200, 0)
            )

        # Draw Hand Connections
        if pose_frame.left_hand_21:
            landmarks = self._to_mediapipe_normalized(pose_frame.left_hand_21, w, h)
            annotated = self._draw_connections(
                annotated, landmarks, self.HAND_CONNECTIONS, (0, 255, 0)
            )
        if pose_frame.right_hand_21:
            landmarks = self._to_mediapipe_normalized(pose_frame.right_hand_21, w, h)
            annotated = self._draw_connections(
                annotated, landmarks, self.HAND_CONNECTIONS, (255, 0, 255)
            )

        # Draw HUD overlay info text
        cv2.putText(
            annotated,
            f"Frame {pose_frame.frame_id} | Conf: {pose_frame.confidence:.2f}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
        )

        return annotated

    @staticmethod
    def _landmarks_to_list(landmarks, w: int, h: int) -> List[dict]:
        if landmarks is None:
            return []
        return [
            {
                "x": lm.x * w,
                "y": lm.y * h,
                "z": lm.z * w,
                "v": getattr(lm, "visibility", 1.0) or 1.0,
            }
            for lm in landmarks.landmark
        ]

    @staticmethod
    def _to_mediapipe_normalized(landmarks: List[Landmark], w: int, h: int):
        """Reconstruct MediaPipe proto structures for connection drawing"""
        from mediapipe.framework.formats import landmark_pb2
        proto = landmark_pb2.NormalizedLandmarkList()
        for lm in landmarks:
            proto.landmark.add(
                x=lm.x / w, y=lm.y / h, z=lm.z / w, visibility=lm.v
            )
        return proto

    @staticmethod
    def _draw_connections(frame: np.ndarray, landmarks, connections, color: Tuple[int, int, int]) -> np.ndarray:
        """Manual connection and node drawing using standard OpenCV circle/line methods"""
        h, w = frame.shape[:2]
        points = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks.landmark]
        for conn in connections:
            start_idx, end_idx = conn
            if start_idx < len(points) and end_idx < len(points):
                cv2.line(frame, points[start_idx], points[end_idx], color, 2)
        for pt in points:
            cv2.circle(frame, pt, 3, color, -1)
        return frame

    def close(self):
        self.holistic.close()
