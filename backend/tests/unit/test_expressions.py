"""
Unit tests for facial expression analyzer.
"""
import pytest
from backend.services.perception.expressions import (
    ExpressionAnalyzer, Expression, FACE
)


def make_face_landmarks(ear=0.2, mar=0.15, smile_intensity=0.0, brow_to_eye=10.0):
    """
    Create synthetic face landmarks.
    """
    # Create 478 blank landmarks
    landmarks = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(478)]
    
    # eyes
    landmarks[FACE.LEFT_EYE_LEFT] = {"x": -20.0, "y": -10.0, "z": 0.0}
    landmarks[FACE.LEFT_EYE_RIGHT] = {"x": -10.0, "y": -10.0, "z": 0.0}
    landmarks[FACE.RIGHT_EYE_LEFT] = {"x": 10.0, "y": -10.0, "z": 0.0}
    landmarks[FACE.RIGHT_EYE_RIGHT] = {"x": 20.0, "y": -10.0, "z": 0.0}
    
    # Calculate Y coordinates for eye top/bottom based on EAR
    # EAR = vertical / horizontal. horizontal is 10. vertical = EAR * 10
    vert_eye = ear * 10
    landmarks[FACE.LEFT_EYE_TOP] = {"x": -15.0, "y": -10.0 - vert_eye / 2, "z": 0.0}
    landmarks[FACE.LEFT_EYE_BOTTOM] = {"x": -15.0, "y": -10.0 + vert_eye / 2, "z": 0.0}
    landmarks[FACE.RIGHT_EYE_TOP] = {"x": 15.0, "y": -10.0 - vert_eye / 2, "z": 0.0}
    landmarks[FACE.RIGHT_EYE_BOTTOM] = {"x": 15.0, "y": -10.0 + vert_eye / 2, "z": 0.0}
    
    # Mouth corners
    landmarks[FACE.MOUTH_LEFT] = {"x": -15.0, "y": 20.0, "z": 0.0}
    landmarks[FACE.MOUTH_RIGHT] = {"x": 15.0, "y": 20.0, "z": 0.0}
    
    # Mouth top/bottom (MAR)
    # MAR = vertical / horizontal. horizontal is 30. vertical = MAR * 30
    vert_mouth = mar * 30
    landmarks[FACE.MOUTH_TOP] = {"x": 0.0, "y": 20.0 - vert_mouth / 2, "z": 0.0}
    landmarks[FACE.MOUTH_BOTTOM] = {"x": 0.0, "y": 20.0 + vert_mouth / 2, "z": 0.0}
    
    # Upper lip top
    # Smile intensity = (upper_lip_y - mouth_corner_avg_y) / mouth_width
    # mouth_width is 30. upper_lip_y = mouth_corner_avg_y + smile_intensity * 30
    # mouth_corner_avg_y is 20.
    upper_lip_y = 20.0 + smile_intensity * 30
    landmarks[FACE.UPPER_LIP_TOP] = {"x": 0.0, "y": upper_lip_y, "z": 0.0}
    landmarks[FACE.LOWER_LIP_BOTTOM] = {"x": 0.0, "y": 25.0, "z": 0.0}
    
    # Eyebrows
    # brow_to_eye = eye_top_y - brow_avg_y
    # eye_top_y is -10 - vert_eye/2. brow_avg_y = eye_top_y - brow_to_eye
    eye_top_y = -10.0 - vert_eye / 2
    brow_y = eye_top_y - brow_to_eye
    landmarks[FACE.LEFT_BROW_INNER] = {"x": -5.0, "y": brow_y, "z": 0.0}
    landmarks[FACE.RIGHT_BROW_INNER] = {"x": 5.0, "y": brow_y, "z": 0.0}
    
    # Nose, Chin, Forehead (for head pose)
    landmarks[FACE.NOSE_TIP] = {"x": 0.0, "y": 0.0, "z": -10.0}
    landmarks[FACE.CHIN] = {"x": 0.0, "y": 40.0, "z": 0.0}
    landmarks[FACE.FOREHEAD] = {"x": 0.0, "y": -30.0, "z": 0.0}
    
    return landmarks


@pytest.mark.unit
class TestExpressionAnalyzer:
    """Tests for facial expression analysis."""
    
    def test_neutral_default(self):
        """Standard face yields NEUTRAL."""
        analyzer = ExpressionAnalyzer()
        landmarks = make_face_landmarks(ear=0.2, mar=0.15, smile_intensity=0.0, brow_to_eye=10)
        res = analyzer.analyze(landmarks)
        assert res["expression"] == Expression.NEUTRAL.value
    
    def test_happy(self):
        """Smile intensity and wide mouth yields HAPPY."""
        analyzer = ExpressionAnalyzer()
        landmarks = make_face_landmarks(ear=0.2, mar=0.15, smile_intensity=0.05, brow_to_eye=10)
        res = analyzer.analyze(landmarks)
        assert res["expression"] == Expression.HAPPY.value
        assert res["confidence"] > 0.0
    
    def test_surprised(self):
        """Wide eyes, open mouth, raised brows yields SURPRISED."""
        analyzer = ExpressionAnalyzer()
        landmarks = make_face_landmarks(ear=0.35, mar=0.6, smile_intensity=-0.01, brow_to_eye=20)
        res = analyzer.analyze(landmarks)
        assert res["expression"] == Expression.SURPRISED.value
    
    def test_too_few_landmarks(self):
        """Fewer than 300 points yields NEUTRAL with 0.0 confidence."""
        analyzer = ExpressionAnalyzer()
        res = analyzer.analyze([])
        assert res["expression"] == Expression.NEUTRAL.value
        assert res["confidence"] == 0.0
    
    def test_head_pose_estimation(self):
        """Verify pitch, yaw, and roll are in degrees."""
        analyzer = ExpressionAnalyzer()
        landmarks = make_face_landmarks()
        res = analyzer.analyze(landmarks)
        assert "pitch" in res["head_pose"]
        assert "yaw" in res["head_pose"]
        assert "roll" in res["head_pose"]
        assert isinstance(res["head_pose"]["pitch"], float)
