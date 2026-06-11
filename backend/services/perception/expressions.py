"""
Facial expression analysis using geometric features of face mesh.
Detects 7 basic emotions (Ekman) + neutral + head pose.
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from enum import Enum


class Expression(Enum):
    """Ekman's 7 basic emotions + neutral."""
    NEUTRAL = "NEUTRAL"
    HAPPY = "HAPPY"
    SAD = "SAD"
    ANGRY = "ANGRY"
    SURPRISED = "SURPRISED"
    FEARFUL = "FEARFUL"
    DISGUSTED = "DISGUSTED"
    CONTEMPT = "CONTEMPT"


# MediaPipe face mesh landmark indices
class FACE:
    # Eyes
    LEFT_EYE_TOP = 159
    LEFT_EYE_BOTTOM = 145
    LEFT_EYE_LEFT = 33
    LEFT_EYE_RIGHT = 133
    RIGHT_EYE_TOP = 386
    RIGHT_EYE_BOTTOM = 374
    RIGHT_EYE_LEFT = 362
    RIGHT_EYE_RIGHT = 263

    # Eyebrows
    LEFT_BROW_INNER = 107
    LEFT_BROW_OUTER = 66
    RIGHT_BROW_INNER = 336
    RIGHT_BROW_OUTER = 296

    # Mouth
    MOUTH_LEFT = 61
    MOUTH_RIGHT = 291
    MOUTH_TOP = 13
    MOUTH_BOTTOM = 14
    UPPER_LIP_TOP = 0
    LOWER_LIP_BOTTOM = 17
    MOUTH_CENTER_TOP = 13
    MOUTH_CENTER_BOTTOM = 14

    # Nose
    NOSE_TIP = 1
    NOSE_BASE = 2

    # Chin
    CHIN = 152

    # Forehead
    FOREHEAD = 10


class ExpressionAnalyzer:
    """
    Analyzes facial expressions from 478-point face mesh.
    Uses geometric feature extraction + heuristic rules.
    """

    def analyze(self, face_landmarks: List[Dict]) -> Dict:
        """
        Analyze facial expression.
        Returns: {
            'expression': Expression enum value,
            'confidence': float (0-1),
            'head_pose': {pitch, yaw, roll} in degrees,
            'gaze': {'direction': 'left'|'right'|'center'|'up'|'down', 'target': str}
        }
        """
        if len(face_landmarks) < 300: # Need enough face mesh coordinates
            return {
                "expression": Expression.NEUTRAL.value,
                "confidence": 0.0,
                "head_pose": {"pitch": 0, "yaw": 0, "roll": 0},
                "gaze": {"direction": "center", "target": "unknown"},
            }

        # Extract geometric features
        features = self._extract_features(face_landmarks)

        # Classify expression
        expression, confidence = self._classify_expression(features)

        # Compute head pose
        head_pose = self._compute_head_pose(face_landmarks)

        # Compute gaze direction
        gaze = self._compute_gaze(face_landmarks)

        return {
            "expression": expression.value,
            "confidence": round(confidence, 3),
            "head_pose": head_pose,
            "gaze": gaze,
        }

    def _extract_features(self, landmarks: List[Dict]) -> Dict:
        """
        Extract facial action units (AUs) from landmarks.
        """
        # Helper to get coord values supporting both object attributes and dict lookups
        def get_y(idx):
            lm = landmarks[idx]
            return lm.y if hasattr(lm, 'y') else lm.get('y', 0.0)

        # Eye aspect ratio (EAR) - how open are eyes
        left_ear = self._eye_aspect_ratio(
            landmarks[FACE.LEFT_EYE_TOP],
            landmarks[FACE.LEFT_EYE_BOTTOM],
            landmarks[FACE.LEFT_EYE_LEFT],
            landmarks[FACE.LEFT_EYE_RIGHT],
        )
        right_ear = self._eye_aspect_ratio(
            landmarks[FACE.RIGHT_EYE_TOP],
            landmarks[FACE.RIGHT_EYE_BOTTOM],
            landmarks[FACE.RIGHT_EYE_LEFT],
            landmarks[FACE.RIGHT_EYE_RIGHT],
        )
        avg_ear = (left_ear + right_ear) / 2

        # Mouth aspect ratio (MAR) - how open is mouth
        mar = self._mouth_aspect_ratio(landmarks)

        # Mouth width vs height
        mouth_width = self._dist(landmarks[FACE.MOUTH_LEFT], landmarks[FACE.MOUTH_RIGHT])
        mouth_height = self._dist(landmarks[FACE.MOUTH_TOP], landmarks[FACE.MOUTH_BOTTOM])
        mouth_ratio = mouth_width / (mouth_height + 1e-6)

        # Smile detection (mouth corners raised)
        mouth_corner_avg_y = (get_y(FACE.MOUTH_LEFT) + get_y(FACE.MOUTH_RIGHT)) / 2
        upper_lip_y = get_y(FACE.UPPER_LIP_TOP)
        smile_intensity = (upper_lip_y - mouth_corner_avg_y) / (mouth_width + 1e-6)

        # Brow position (furrowed = angry)
        left_brow_y = get_y(FACE.LEFT_BROW_INNER)
        right_brow_y = get_y(FACE.RIGHT_BROW_INNER)
        eye_top_y = (get_y(FACE.LEFT_EYE_TOP) + get_y(FACE.RIGHT_EYE_TOP)) / 2
        brow_to_eye = eye_top_y - (left_brow_y + right_brow_y) / 2
        # Higher value = brows raised (surprise), lower or negative = brows down (anger)

        # Nose wrinkle (disgust)
        nose_to_upper_lip = self._dist(landmarks[FACE.NOSE_TIP], landmarks[FACE.UPPER_LIP_TOP])

        return {
            "ear": avg_ear,
            "mar": mar,
            "mouth_ratio": mouth_ratio,
            "smile_intensity": smile_intensity,
            "brow_to_eye": brow_to_eye,
            "nose_to_lip": nose_to_upper_lip,
        }

    def _classify_expression(self, f: Dict) -> Tuple[Expression, float]:
        """
        Rule-based expression classification.
        Returns (expression, confidence).
        """
        # Happy: smile + moderate eye openness
        if f["smile_intensity"] > 0.02 and f["mouth_ratio"] > 3.0 and f["ear"] > 0.15:
            return Expression.HAPPY, min(0.95, f["smile_intensity"] * 10)

        # Surprised: wide eyes + open mouth + raised brows
        if f["ear"] > 0.30 and f["mar"] > 0.5 and f["brow_to_eye"] > 15:
            return Expression.SURPRISED, 0.92

        # Sad: low mouth corners + drooping features
        if f["smile_intensity"] < -0.02 and f["ear"] < 0.18:
            return Expression.SAD, 0.75

        # Angry: lowered brows + tight mouth
        if f["brow_to_eye"] < 5 and f["mouth_ratio"] < 3.0 and f["mar"] < 0.3:
            return Expression.ANGRY, 0.78

        # Disgusted: wrinkled nose + raised upper lip
        if f["nose_to_lip"] < 15 and f["mar"] > 0.1 and f["smile_intensity"] < 0:
            return Expression.DISGUSTED, 0.72

        # Fearful: wide eyes + tense mouth
        if f["ear"] > 0.28 and f["mar"] > 0.2 and f["brow_to_eye"] > 8:
            return Expression.FEARFUL, 0.70

        return Expression.NEUTRAL, 0.6

    def _compute_head_pose(self, landmarks: List[Dict]) -> Dict:
        """
        Estimate head pose (pitch, yaw, roll) from face landmarks.
        Uses nose, chin, and eye corners for estimation.
        """
        def get_arr(idx):
            lm = landmarks[idx]
            lx = lm.x if hasattr(lm, 'x') else lm.get('x', 0.0)
            ly = lm.y if hasattr(lm, 'y') else lm.get('y', 0.0)
            lz = lm.z if hasattr(lm, 'z') else lm.get('z', 0.0)
            return np.array([lx, ly, lz])

        nose = get_arr(FACE.NOSE_TIP)
        chin = get_arr(FACE.CHIN)
        forehead = get_arr(FACE.FOREHEAD)

        left_eye = get_arr(FACE.LEFT_EYE_LEFT)
        right_eye = get_arr(FACE.RIGHT_EYE_LEFT)

        # Yaw: left-right rotation (using eye distance + nose offset)
        eye_mid = (left_eye + right_eye) / 2
        nose_offset = nose[0] - eye_mid[0]
        eye_distance = np.linalg.norm(right_eye - left_eye) + 1e-6
        yaw = np.degrees(np.arctan2(nose_offset, eye_distance * 2))

        # Pitch: up-down rotation (using forehead-nose-chin triangle)
        vertical = chin - forehead
        forward = nose - (forehead + chin) / 2
        pitch = np.degrees(np.arctan2(forward[1], np.linalg.norm(forward[:2])))

        # Roll: tilt (eye line angle)
        roll = np.degrees(np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))

        return {
            "pitch": round(float(pitch), 1),
            "yaw": round(float(yaw), 1),
            "roll": round(float(roll), 1),
        }

    def _compute_gaze(self, landmarks: List[Dict]) -> Dict:
        """
        Estimate gaze direction from iris position.
        """
        def get_val(idx, coord):
            lm = landmarks[idx]
            return getattr(lm, coord) if hasattr(lm, coord) else lm.get(coord, 0.0)

        # Use iris landmarks (468-477 if refined, else approximate from eye corners)
        left_iris_x = (get_val(FACE.LEFT_EYE_LEFT, 'x') + get_val(FACE.LEFT_EYE_RIGHT, 'x')) / 2
        left_eye_center = (get_val(FACE.LEFT_EYE_LEFT, 'x') + get_val(FACE.LEFT_EYE_RIGHT, 'x')) / 2

        right_iris_x = (get_val(FACE.RIGHT_EYE_LEFT, 'x') + get_val(FACE.RIGHT_EYE_RIGHT, 'x')) / 2
        right_eye_center = (get_val(FACE.RIGHT_EYE_LEFT, 'x') + get_val(FACE.RIGHT_EYE_RIGHT, 'x')) / 2

        # Average gaze offset
        avg_offset = ((left_iris_x - left_eye_center) + (right_iris_x - right_eye_center)) / 2
        eye_width = abs(get_val(FACE.LEFT_EYE_RIGHT, 'x') - get_val(FACE.LEFT_EYE_LEFT, 'x')) + 1e-6
        normalized_offset = avg_offset / eye_width

        # Vertical gaze (using top/bottom of eye)
        left_iris_y = (get_val(FACE.LEFT_EYE_TOP, 'y') + get_val(FACE.LEFT_EYE_BOTTOM, 'y')) / 2
        left_eye_center_y = (get_val(FACE.LEFT_EYE_TOP, 'y') + get_val(FACE.LEFT_EYE_BOTTOM, 'y')) / 2
        v_offset = (left_iris_y - left_eye_center_y) / eye_width

        # Classify direction
        direction = "center"
        if abs(normalized_offset) > 0.3:
            direction = "right" if normalized_offset > 0 else "left"
        if abs(v_offset) > 0.3:
            direction = "up" if v_offset < 0 else "down"

        return {
            "direction": direction,
            "horizontal_offset": round(float(normalized_offset), 2),
            "vertical_offset": round(float(v_offset), 2),
            "target": "unknown",  # Filled in by interaction engine
        }

    @staticmethod
    def _dist(a: Dict, b: Dict) -> float:
        ax = a.x if hasattr(a, 'x') else a.get('x', 0.0)
        ay = a.y if hasattr(a, 'y') else a.get('y', 0.0)
        az = a.z if hasattr(a, 'z') else a.get('z', 0.0)
        bx = b.x if hasattr(b, 'x') else b.get('x', 0.0)
        by = b.y if hasattr(b, 'y') else b.get('y', 0.0)
        bz = b.z if hasattr(b, 'z') else b.get('z', 0.0)
        return ((ax - bx)**2 + (ay - by)**2 + (az - bz)**2) ** 0.5

    @staticmethod
    def _eye_aspect_ratio(top, bottom, left, right) -> float:
        """Eye aspect ratio (EAR)."""
        def get_pos(lm):
            lx = lm.x if hasattr(lm, 'x') else lm.get('x', 0.0)
            ly = lm.y if hasattr(lm, 'y') else lm.get('y', 0.0)
            return np.array([lx, ly])
        
        vertical = np.linalg.norm(get_pos(top) - get_pos(bottom))
        horizontal = np.linalg.norm(get_pos(left) - get_pos(right))
        return float(vertical / (horizontal + 1e-6))

    @staticmethod
    def _mouth_aspect_ratio(landmarks: List[Dict]) -> float:
        """Mouth aspect ratio (MAR)."""
        def get_y(idx):
            lm = landmarks[idx]
            return lm.y if hasattr(lm, 'y') else lm.get('y', 0.0)
        def get_x(idx):
            lm = landmarks[idx]
            return lm.x if hasattr(lm, 'x') else lm.get('x', 0.0)
            
        vertical = abs(get_y(FACE.MOUTH_TOP) - get_y(FACE.MOUTH_BOTTOM))
        horizontal = abs(get_x(FACE.MOUTH_LEFT) - get_x(FACE.MOUTH_RIGHT))
        return float(vertical / (horizontal + 1e-6))
