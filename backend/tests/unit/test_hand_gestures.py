"""
Unit tests for hand gesture classifier.
"""
import pytest
from backend.services.perception.hand_gestures import (
    HandGestureClassifier, HandGesture
)


def make_hand_landmarks(fingers_state):
    """
    Create synthetic hand landmarks.
    fingers_state: dict like {"thumb": True, "index": False, ...}
    """
    landmarks = []
    for i in range(21):
        lm = {"x": float(i * 10), "y": float(i * 5), "z": 0.0, "v": 1.0}
        landmarks.append(lm)
    
    # Base MCP values for relative comparisons in heuristics
    landmarks[0] = {"x": 0.0, "y": 0.0, "z": 0.0, "v": 1.0}  # wrist
    landmarks[9] = {"x": 0.0, "y": -50.0, "z": 0.0, "v": 1.0}  # middle MCP (for hand size reference)
    
    # Thumb base & tip
    landmarks[2] = {"x": 30.0, "y": -20.0, "z": 0.0, "v": 1.0}
    if fingers_state.get("thumb"):
        landmarks[4] = {"x": 60.0, "y": -20.0, "z": 0.0, "v": 1.0}  # far
    else:
        landmarks[4] = {"x": 20.0, "y": -40.0, "z": 0.0, "v": 1.0}  # close
        
    # Index finger: mcp at 5, tip at 8
    landmarks[5] = {"x": 10.0, "y": -50.0, "z": 0.0, "v": 1.0}
    if fingers_state.get("index"):
        landmarks[8] = {"x": 10.0, "y": -120.0, "z": 0.0, "v": 1.0}  # tip far from base
    else:
        landmarks[8] = {"x": 10.0, "y": -40.0, "z": 0.0, "v": 1.0}   # tip close to wrist/MCP
    
    # Middle finger: mcp at 9, tip at 12
    landmarks[9] = {"x": 0.0, "y": -50.0, "z": 0.0, "v": 1.0}
    if fingers_state.get("middle"):
        landmarks[12] = {"x": 0.0, "y": -130.0, "z": 0.0, "v": 1.0}
    else:
        landmarks[12] = {"x": 0.0, "y": -40.0, "z": 0.0, "v": 1.0}
    
    # Ring finger: mcp at 13, tip at 16
    landmarks[13] = {"x": -10.0, "y": -50.0, "z": 0.0, "v": 1.0}
    if fingers_state.get("ring"):
        landmarks[16] = {"x": -10.0, "y": -120.0, "z": 0.0, "v": 1.0}
    else:
        landmarks[16] = {"x": -10.0, "y": -40.0, "z": 0.0, "v": 1.0}
    
    # Pinky: mcp at 17, tip at 20
    landmarks[17] = {"x": -20.0, "y": -50.0, "z": 0.0, "v": 1.0}
    if fingers_state.get("pinky"):
        landmarks[20] = {"x": -20.0, "y": -110.0, "z": 0.0, "v": 1.0}
    else:
        landmarks[20] = {"x": -20.0, "y": -40.0, "z": 0.0, "v": 1.0}
    
    return landmarks


@pytest.mark.unit
class TestHandGestureClassifier:
    """Tests for hand gesture classification."""
    
    def test_open_palm(self):
        """All fingers extended = OPEN_PALM."""
        clf = HandGestureClassifier()
        landmarks = make_hand_landmarks({
            "thumb": True, "index": True, "middle": True,
            "ring": True, "pinky": True
        })
        assert clf.classify(landmarks) == HandGesture.OPEN_PALM.value
    
    def test_fist(self):
        """All fingers curled = FIST."""
        clf = HandGestureClassifier()
        landmarks = make_hand_landmarks({
            "thumb": False, "index": False, "middle": False,
            "ring": False, "pinky": False
        })
        assert clf.classify(landmarks) == HandGesture.FIST.value
    
    def test_pointing(self):
        """Index extended, others curled = POINTING."""
        clf = HandGestureClassifier()
        landmarks = make_hand_landmarks({
            "thumb": False, "index": True, "middle": False,
            "ring": False, "pinky": False
        })
        assert clf.classify(landmarks) == HandGesture.POINTING.value
    
    def test_peace(self):
        """Index + middle extended, others curled = PEACE."""
        clf = HandGestureClassifier()
        landmarks = make_hand_landmarks({
            "thumb": False, "index": True, "middle": True,
            "ring": False, "pinky": False
        })
        assert clf.classify(landmarks) == HandGesture.PEACE.value
    
    def test_unknown_too_few_landmarks(self):
        """Too few landmarks = UNKNOWN."""
        clf = HandGestureClassifier()
        assert clf.classify([]) == HandGesture.UNKNOWN.value
        assert clf.classify([{"x": 0, "y": 0, "z": 0, "v": 1}] * 5) == HandGesture.UNKNOWN.value
    
    def test_bimanual_two_hands(self):
        """Should detect bimanual patterns."""
        clf = HandGestureClassifier()
        left = make_hand_landmarks({"thumb": True, "index": True, "middle": True, "ring": True, "pinky": True})
        right = make_hand_landmarks({"thumb": True, "index": True, "middle": True, "ring": True, "pinky": True})
        
        result = clf.classify_both_hands(left, right)
        assert result["left_hand"] == HandGesture.OPEN_PALM.value
        assert result["right_hand"] == HandGesture.OPEN_PALM.value
        assert result["bimanual_pattern"] == "BOTH_HANDS_UP"
    
    def test_bimanual_no_hands(self):
        """No hands = None values."""
        clf = HandGestureClassifier()
        result = clf.classify_both_hands(None, None)
        assert result["left_hand"] is None
        assert result["right_hand"] is None
        assert result["bimanual_pattern"] is None
