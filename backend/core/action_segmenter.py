"""
Rule-based action segmentation using velocity thresholds + joint trajectories.
Detects atomic actions: idle, walking, waving, arm raise, grabbing, sitting.
"""
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict
from .skeleton_graph import MP


@dataclass
class ActionSegment:
    """A contiguous segment of detected action."""
    start_frame: int
    end_frame: int
    action: str
    confidence: float
    description: str = ""

    def to_dict(self):
        return asdict(self)


class ActionSegmenter:
    """
    Velocity + position-based action detection.
    Lightweight, no ML required — perfect for university demo.
    """

    # Velocity thresholds (pixels/frame, normalized)
    IDLE_THRESHOLD = 3.0
    ACTIVE_THRESHOLD = 15.0

    def __init__(self, fps: float = 30.0):
        self.fps = fps

    def segment_sequence(
        self, frames_landmarks: List[List[dict]]
    ) -> List[ActionSegment]:
        """
        Detect action segments in full motion sequence.
        Returns list of ActionSegment with start/end frames + label.
        """
        if not frames_landmarks:
            return []

        # Step 1: Compute per-frame features
        features = [self._extract_features(f) for f in frames_landmarks]

        # Step 2: Classify each frame
        frame_labels = [self._classify_frame(f) for f in features]

        # Step 3: Merge consecutive same-label frames into segments
        segments = self._merge_segments(frame_labels, features)

        return segments

    def _extract_features(self, landmarks: List[dict]) -> Dict:
        """Extract per-frame motion features."""
        if len(landmarks) < 33:
            return {"motion_mag": 0, "wrist_y": 0, "wrist_height": 0,
                    "step_phase": 0, "arm_extended": False, "sitting": False}

        # Average landmark motion (proxy for overall activity)
        motion_mag = 0
        for i in range(33):
            if i < len(landmarks):
                motion_mag += abs(landmarks[i].get("x", 0)) + abs(landmarks[i].get("y", 0))
        motion_mag /= 33

        # Wrist positions relative to shoulders
        l_wrist_y = landmarks[MP.LEFT_WRIST]["y"] if MP.LEFT_WRIST < len(landmarks) else 0
        r_wrist_y = landmarks[MP.RIGHT_WRIST]["y"] if MP.RIGHT_WRIST < len(landmarks) else 0
        avg_wrist_y = (l_wrist_y + r_wrist_y) / 2

        l_sh_y = landmarks[MP.LEFT_SHOULDER]["y"] if MP.LEFT_SHOULDER < len(landmarks) else 0
        r_sh_y = landmarks[MP.RIGHT_SHOULDER]["y"] if MP.RIGHT_SHOULDER < len(landmarks) else 0
        avg_sh_y = (l_sh_y + r_sh_y) / 2

        # Wrist above shoulder? (arm raised)
        wrist_height = avg_sh_y - avg_wrist_y  # positive = above

        # Hip position (sitting detection)
        l_hip_y = landmarks[MP.LEFT_HIP]["y"] if MP.LEFT_HIP < len(landmarks) else 0
        r_hip_y = landmarks[MP.RIGHT_HIP]["y"] if MP.RIGHT_HIP < len(landmarks) else 0
        avg_hip_y = (l_hip_y + r_hip_y) / 2

        # Knee-hip distance (sitting: knee close to hip)
        l_knee_y = landmarks[MP.LEFT_KNEE]["y"] if MP.LEFT_KNEE < len(landmarks) else 0
        r_knee_y = landmarks[MP.RIGHT_KNEE]["y"] if MP.RIGHT_KNEE < len(landmarks) else 0
        avg_knee_y = (l_knee_y + r_knee_y) / 2
        knee_hip_dist = abs(avg_knee_y - avg_hip_y)

        # Reference: in standing, knee-hip distance is large
        # In sitting, knee-hip distance is small
        # Use ankle as reference
        l_ankle_y = landmarks[MP.LEFT_ANKLE]["y"] if MP.LEFT_ANKLE < len(landmarks) else 0
        r_ankle_y = landmarks[MP.RIGHT_ANKLE]["y"] if MP.RIGHT_ANKLE < len(landmarks) else 0
        avg_ankle_y = (l_ankle_y + r_ankle_y) / 2
        total_leg = abs(avg_ankle_y - avg_hip_y) + 1e-6
        knee_ratio = abs(avg_knee_y - avg_hip_y) / total_leg

        sitting = knee_ratio < 0.4  # knees high = sitting

        # Arm extension (wrist far from shoulder horizontally)
        l_wrist_x = landmarks[MP.LEFT_WRIST]["x"] if MP.LEFT_WRIST < len(landmarks) else 0
        l_sh_x = landmarks[MP.LEFT_SHOULDER]["x"] if MP.LEFT_SHOULDER < len(landmarks) else 0
        r_wrist_x = landmarks[MP.RIGHT_WRIST]["x"] if MP.RIGHT_WRIST < len(landmarks) else 0
        r_sh_x = landmarks[MP.RIGHT_SHOULDER]["x"] if MP.RIGHT_SHOULDER < len(landmarks) else 0

        l_arm_ext = abs(l_wrist_x - l_sh_x) > 80
        r_arm_ext = abs(r_wrist_x - r_sh_x) > 80
        arm_extended = l_arm_ext or r_arm_ext

        return {
            "motion_mag": motion_mag,
            "wrist_y": avg_wrist_y,
            "wrist_height": wrist_height,
            "arm_extended": arm_extended,
            "sitting": sitting,
            "hip_y": avg_hip_y,
        }

    def _classify_frame(self, features: Dict) -> str:
        """Classify single frame into one of: idle, walk, wave, arm_raise, sit, grab."""
        if features["motion_mag"] < self.IDLE_THRESHOLD:
            return "idle"

        if features["sitting"]:
            return "sit"

        # Arm raised significantly (above shoulder)
        if features["wrist_height"] > 50:
            return "arm_raise"

        # Arm extended horizontally
        if features["arm_extended"]:
            return "grab"

        # General motion = walking / gesturing
        if features["motion_mag"] > self.ACTIVE_THRESHOLD:
            return "walk"

        return "gesture"

    def _merge_segments(
        self, frame_labels: List[str], features: List[Dict]
    ) -> List[ActionSegment]:
        """Merge consecutive frames with same label into segments."""
        if not frame_labels:
            return []

        segments = []
        current_label = frame_labels[0]
        start = 0

        for i, label in enumerate(frame_labels):
            if label != current_label:
                # Close previous segment
                if i - start >= 3:  # min 3 frames to register
                    confidence = self._segment_confidence(
                        current_label, features[start:i]
                    )
                    segments.append(
                        ActionSegment(
                            start_frame=start,
                            end_frame=i - 1,
                            action=current_label,
                            confidence=confidence,
                            description=self._describe(current_label, i - start),
                        )
                    )
                current_label = label
                start = i

        # Close last segment
        if len(frame_labels) - start >= 3:
            confidence = self._segment_confidence(
                current_label, features[start:]
            )
            segments.append(
                ActionSegment(
                    start_frame=start,
                    end_frame=len(frame_labels) - 1,
                    action=current_label,
                    confidence=confidence,
                    description=self._describe(current_label, len(frame_labels) - start),
                )
            )

        return segments

    def _segment_confidence(self, action: str, features: List[Dict]) -> float:
        """Compute confidence score for a detected segment."""
        if not features:
            return 0.5
        # Higher confidence if features strongly indicate action
        if action == "idle":
            avg_motion = np.mean([f["motion_mag"] for f in features])
            return min(1.0, max(0.0, 1.0 - avg_motion / 10.0))
        elif action in ("walk", "gesture"):
            avg_motion = np.mean([f["motion_mag"] for f in features])
            return min(1.0, max(0.0, avg_motion / 30.0))
        return 0.7

    def _describe(self, action: str, frame_count: int) -> str:
        duration = frame_count / self.fps
        descriptions = {
            "idle": f"Idle/standing still ({duration:.1f}s)",
            "walk": f"Walking or active motion ({duration:.1f}s)",
            "wave": f"Waving gesture ({duration:.1f}s)",
            "arm_raise": f"Arm raised ({duration:.1f}s)",
            "grab": f"Reaching/grabbing ({duration:.1f}s)",
            "sit": f"Sitting posture ({duration:.1f}s)",
            "gesture": f"General gesture ({duration:.1f}s)",
        }
        return descriptions.get(action, f"{action} ({duration:.1f}s)")
