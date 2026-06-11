import cv2
import mediapipe as mp
import numpy as np
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import json

# Selected facial landmark indices for expressing eyes, eyebrows, nose, and lips (approx. 90 points)
FACE_KEY_LANDMARKS = [
    # Lip outer contour
    61, 185, 40, 39, 37, 0, 267, 269, 270, 291, 321, 375, 405, 314, 17, 84, 181, 91, 146,
    # Lip inner contour
    78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 95, 88,
    # Left eye outline
    33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7,
    # Right eye outline
    263, 466, 388, 387, 386, 385, 384, 398, 362, 382, 381, 380, 374, 373, 390, 249,
    # Left eyebrow
    70, 63, 105, 66, 107, 55, 65, 52, 53, 46,
    # Right eyebrow
    300, 293, 334, 296, 336, 285, 295, 282, 283, 276,
    # Nose outline
    168, 6, 197, 195, 5, 4, 1, 19, 94, 2, 98, 97, 326, 327, 294, 278
]

@dataclass
class PoseFrame:
    """Single frame pose data"""
    frame_id: int
    timestamp: float
    landmarks_33: List[Dict[str, float]]    # Body pose (33 points)
    left_hand_21: List[Dict[str, float]]    # Left hand (21 points)
    right_hand_21: List[Dict[str, float]]   # Right hand (21 points)
    face_mesh: List[Dict[str, float]]       # Key face contour & expression landmarks (90 points)
    joint_angles: Dict[str, float] = None   # Extracted joint angles (calculated post-capture)
    
    def to_dict(self):
        d = asdict(self)
        if d.get('joint_angles') is None:
            d['joint_angles'] = {}
        return d

class PoseExtractor:
    """Unified pose extraction using MediaPipe Solutions"""
    
    def __init__(self, 
                 model_complexity: int = 1,
                 smooth_landmarks: bool = True):
        self.mp_pose = mp.solutions.pose
        self.mp_hands = mp.solutions.hands
        self.mp_face = mp.solutions.face_mesh
        
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            smooth_landmarks=smooth_landmarks,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.face = self.mp_face.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
    
    def extract_frame(self, frame: np.ndarray, frame_id: int) -> PoseFrame:
        """Extract all landmarks from single frame"""
        # MediaPipe requires RGB images
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        
        # 1. Pose Landmarks (Body)
        pose_results = self.pose.process(rgb)
        pose_lms = self._format_pose_landmarks(pose_results.pose_landmarks)
        
        # 2. Hand Landmarks
        hand_results = self.hands.process(rgb)
        left_hand, right_hand = self._process_hands(hand_results)
        
        # 3. Face Mesh Landmarks
        face_results = self.face.process(rgb)
        face_lms = self._format_face_mesh(face_results)
        
        return PoseFrame(
            frame_id=frame_id,
            timestamp=frame_id / 30.0,  # default placeholder, updated in process_video
            landmarks_33=pose_lms,
            left_hand_21=left_hand,
            right_hand_21=right_hand,
            face_mesh=face_lms
        )
    
    def _format_pose_landmarks(self, landmarks) -> List[Dict[str, float]]:
        if not landmarks:
            return []
        # Store normalised landmarks as standard, plus raw screen coords in context
        return [
            {
                "x": lm.x, 
                "y": lm.y, 
                "z": lm.z, 
                "visibility": lm.visibility
            }
            for lm in landmarks.landmark
        ]
    
    def _process_hands(self, results) -> tuple:
        left, right = [], []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return left, right
        
        for idx, hand_lms in enumerate(results.multi_hand_landmarks):
            label = results.multi_handedness[idx].classification[0].label
            formatted = [
                {"x": lm.x, "y": lm.y, "z": lm.z}
                for lm in hand_lms.landmark
            ]
            # MediaPipe's handedness label represents standard left/right camera coordinates
            if label == "Left":
                left = formatted
            else:
                right = formatted
        return left, right
    
    def _format_face_mesh(self, results) -> List[Dict[str, float]]:
        if not results.multi_face_landmarks:
            return []
        lms = results.multi_face_landmarks[0].landmark
        
        # Extract only key expressive and contour landmarks
        formatted = []
        for idx in FACE_KEY_LANDMARKS:
            if idx < len(lms):
                lm = lms[idx]
                formatted.append({"x": lm.x, "y": lm.y, "z": lm.z})
        return formatted
    
    def process_video(self, video_path: str, max_frames: int = 1000, progress_callback=None) -> List[PoseFrame]:
        """Process full video to pose sequence with support for optional progress reporting"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 30.0
            
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = max_frames
            
        frames = []
        frame_id = 0
        
        while cap.isOpened() and frame_id < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
                
            pose_frame = self.extract_frame(frame, frame_id)
            pose_frame.timestamp = frame_id / fps
            frames.append(pose_frame)
            frame_id += 1
            
            if progress_callback:
                progress_percent = min(1.0, frame_id / total_frames)
                progress_callback(frame_id, total_frames, progress_percent)
        
        cap.release()
        return frames
    
    def save_sequence(self, frames: List[PoseFrame], output_path: str, fps: float = 30.0):
        """Save captured sequence as JSON dataset"""
        data = {
            "version": "1.0",
            "frame_count": len(frames),
            "fps": fps,
            "frames": [f.to_dict() for f in frames]
        }
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

    def close(self):
        """Close MediaPipe resources"""
        try:
            self.pose.close()
            self.hands.close()
            self.face.close()
        except Exception:
            pass
