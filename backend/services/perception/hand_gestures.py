"""
Hand gesture classification from 21-landmark hand keypoints.
Uses geometric heuristics - no ML model required.
Detects 12 common gestures.
"""
import numpy as np
from typing import List, Dict, Optional
from enum import Enum


class HandGesture(Enum):
    """Recognized hand gestures."""
    UNKNOWN = "UNKNOWN"
    OPEN_PALM = "OPEN_PALM"           # All fingers extended
    FIST = "FIST"                      # All fingers curled
    POINTING = "POINTING"              # Index extended, others curled
    THUMBS_UP = "THUMBS_UP"            # Thumb up, others curled
    THUMBS_DOWN = "THUMBS_DOWN"        # Thumb down, others curled
    PEACE = "PEACE"                    # Index + middle extended (V sign)
    OK_SIGN = "OK_SIGN"                # Thumb + index circle, others extended
    PINCH = "PINCH"                    # Thumb + index tips touching
    GRAB = "GRAB"                      # All fingers curled but not fully closed
    WAVE = "WAVE"                      # Detected via motion (called externally)
    STOP = "STOP"                      # Open palm facing forward
    CALL_ME = "CALL_ME"                # Thumb + pinky extended


# MediaPipe hand landmark indices
class FINGER:
    WRIST = 0
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_TIP = 20


class HandGestureClassifier:
    """Classify hand gestures from 21-landmark keypoints."""

    def classify(self, landmarks: List[Dict]) -> str:
        """
        Classify gesture from hand landmarks.
        landmarks: list of 21 dicts with {x, y, z, v}
        Returns: HandGesture enum value
        """
        if len(landmarks) < 21:
            return HandGesture.UNKNOWN.value

        # Extract finger extension states
        fingers_extended = self._get_fingers_extended(landmarks)
        thumb_extended, index_ext, middle_ext, ring_ext, pinky_ext = fingers_extended

        # Gesture rules
        if all(fingers_extended):
            return HandGesture.OPEN_PALM.value

        if not any(fingers_extended):
            return HandGesture.FIST.value

        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return HandGesture.POINTING.value

        if not index_ext and not middle_ext and not ring_ext and not pinky_ext and thumb_extended:
            # Check thumb direction (up vs down)
            thumb_tip = landmarks[FINGER.THUMB_TIP]
            wrist = landmarks[FINGER.WRIST]
            
            # Extract x, y, z keys (supporting both objects and dicts)
            def get_y(lm):
                return lm.y if hasattr(lm, 'y') else lm.get('y', 0.0)

            if get_y(thumb_tip) < get_y(wrist):  # y is inverted in image coords
                return HandGesture.THUMBS_UP.value
            return HandGesture.THUMBS_DOWN.value

        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return HandGesture.PEACE.value

        if thumb_extended and pinky_ext and not index_ext and not middle_ext and not ring_ext:
            return HandGesture.CALL_ME.value

        # Check for OK sign (thumb and index tips close together)
        if self._is_pinch(landmarks):
            return HandGesture.OK_SIGN.value

        # Check for grab (partial curl)
        if self._is_grab(landmarks):
            return HandGesture.GRAB.value

        return HandGesture.UNKNOWN.value

    def _get_fingers_extended(self, landmarks: List[Dict]) -> tuple:
        """
        Determine which fingers are extended.
        Returns: (thumb, index, middle, ring, pinky) booleans
        """
        thumb_extended = self._is_thumb_extended(landmarks)
        index_ext = self._is_finger_extended(landmarks, FINGER.INDEX_MCP, FINGER.INDEX_TIP)
        middle_ext = self._is_finger_extended(landmarks, FINGER.MIDDLE_MCP, FINGER.MIDDLE_TIP)
        ring_ext = self._is_finger_extended(landmarks, FINGER.RING_MCP, FINGER.RING_TIP)
        pinky_ext = self._is_finger_extended(landmarks, FINGER.PINKY_MCP, FINGER.PINKY_TIP)

        return (thumb_extended, index_ext, middle_ext, ring_ext, pinky_ext)

    def _is_thumb_extended(self, landmarks: List[Dict]) -> bool:
        """Check if thumb is extended away from palm."""
        thumb_tip = landmarks[FINGER.THUMB_TIP]
        thumb_mcp = landmarks[2]  # Thumb base
        index_mcp = landmarks[FINGER.INDEX_MCP]

        # Distance from thumb tip to index MCP base
        dist = self._dist(thumb_tip, index_mcp)
        thumb_len = self._dist(thumb_tip, thumb_mcp)

        return dist > thumb_len * 1.5

    def _is_finger_extended(self, landmarks: List[Dict], mcp_idx: int, tip_idx: int) -> bool:
        """Check if a finger is extended (tip far from MCP)."""
        mcp = landmarks[mcp_idx]
        tip = landmarks[tip_idx]
        wrist = landmarks[FINGER.WRIST]

        # Compare tip-to-mcp distance to wrist-to-mcp distance
        finger_len = self._dist(tip, mcp)
        palm_len = self._dist(wrist, mcp)

        return finger_len > palm_len * 0.8

    def _is_pinch(self, landmarks: List[Dict]) -> bool:
        """Check if thumb and index tips are touching (OK sign or pinch)."""
        thumb_tip = landmarks[FINGER.THUMB_TIP]
        index_tip = landmarks[FINGER.INDEX_TIP]
        dist = self._dist(thumb_tip, index_tip)

        # Normalize by hand size (wrist to middle MCP)
        hand_size = self._dist(landmarks[FINGER.WRIST], landmarks[FINGER.MIDDLE_MCP])
        return dist < hand_size * 0.3

    def _is_grab(self, landmarks: List[Dict]) -> bool:
        """Check for grab pose (partial curl, fingers not fully closed)."""
        # All fingertips should be below their MCPs (curled)
        # but not too close to palm (which would be fist)
        fingers_curl = []
        for tip_idx, mcp_idx in [(8, 5), (12, 9), (16, 13), (20, 17)]:
            tip = landmarks[tip_idx]
            mcp = landmarks[mcp_idx]
            wrist = landmarks[FINGER.WRIST]

            # Tip should be closer to wrist than MCP is (curled)
            tip_to_wrist = self._dist(tip, wrist)
            mcp_to_wrist = self._dist(mcp, wrist)
            fingers_curl.append(tip_to_wrist < mcp_to_wrist * 1.1)

        return sum(fingers_curl) >= 3  # 3+ fingers curled = grab

    @staticmethod
    def _dist(a: Dict, b: Dict) -> float:
        ax = a.x if hasattr(a, 'x') else a.get('x', 0.0)
        ay = a.y if hasattr(a, 'y') else a.get('y', 0.0)
        az = a.z if hasattr(a, 'z') else a.get('z', 0.0)
        bx = b.x if hasattr(b, 'x') else b.get('x', 0.0)
        by = b.y if hasattr(b, 'y') else b.get('y', 0.0)
        bz = b.z if hasattr(b, 'z') else b.get('z', 0.0)
        return ((ax - bx)**2 + (ay - by)**2 + (az - bz)**2) ** 0.5

    def classify_both_hands(
        self,
        left_landmarks: Optional[List[Dict]],
        right_landmarks: Optional[List[Dict]]
    ) -> Dict:
        """
        Classify gestures for both hands and detect bimanual coordination.
        """
        left_gesture = self.classify(left_landmarks) if left_landmarks else None
        right_gesture = self.classify(right_landmarks) if right_landmarks else None

        # Bimanual patterns
        bimanual = None
        if left_gesture and right_gesture:
            if left_gesture == HandGesture.PINCH.value and right_gesture == HandGesture.GRAB.value:
                bimanual = "TWO_HANDED_HOLD"
            elif left_gesture == HandGesture.OPEN_PALM.value and right_gesture == HandGesture.OPEN_PALM.value:
                bimanual = "BOTH_HANDS_UP"
            elif left_gesture == HandGesture.FIST.value and right_gesture == HandGesture.FIST.value:
                bimanual = "BOTH_FISTS"
            elif left_gesture == HandGesture.POINTING.value and right_gesture == HandGesture.POINTING.value:
                bimanual = "BOTH_POINTING"

        return {
            "left_hand": left_gesture,
            "right_hand": right_gesture,
            "bimanual_pattern": bimanual,
        }
