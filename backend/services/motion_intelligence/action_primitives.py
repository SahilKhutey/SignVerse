"""
Detects atomic action primitives from frame sequence.
Outputs: REACH, GRASP, LIFT, PLACE, PUSH, PULL, TAP, RELEASE.
"""
import numpy as np
from typing import List, Dict, Optional
from collections import deque
from enum import Enum


class Primitive(Enum):
    """Atomic action primitives."""
    IDLE = "IDLE"
    REACH = "REACH"              # Hand moving toward object
    GRASP = "GRASP"              # Hand closing on object
    LIFT = "LIFT"                # Moving object upward
    PLACE = "PLACE"              # Moving object downward
    PUSH = "PUSH"                # Moving object away from body
    PULL = "PULL"                # Moving object toward body
    TAP = "TAP"                  # Quick touch
    RELEASE = "RELEASE"          # Letting go


class ActionPrimitiveDetector:
    """
    Detects atomic actions using rule-based temporal analysis.
    No ML model needed.
    """

    def __init__(self, history_size: int = 10):
        # Track recent states per (hand, object) pair
        self.history_size = history_size
        self.interaction_history: Dict[str, deque] = {}

    def detect(
        self,
        current_interaction_graph: Dict,
        prev_interaction_graph: Optional[Dict] = None,
    ) -> Dict:
        """
        Detect action primitives in current frame.
        Returns: {
            'primitives': [{hand, object, primitive, confidence}],
            'is_transition': bool  # Just changed state
        }
        """
        results = []

        for interaction in current_interaction_graph.get("hand_object_interactions", []):
            key = f"{interaction['hand']}_{interaction['object_id']}"

            # Get or create history
            if key not in self.interaction_history:
                self.interaction_history[key] = deque(maxlen=self.history_size)

            history = self.interaction_history[key]
            history.append(interaction)

            # Need at least 3 frames of history
            if len(history) < 3:
                continue

            # Detect primitive
            primitive, confidence = self._detect_primitive(list(history))

            if primitive != Primitive.IDLE.value:
                results.append({
                    "hand": interaction["hand"],
                    "object_id": interaction["object_id"],
                    "object_class": interaction["object_class"],
                    "primitive": primitive,
                    "confidence": confidence,
                    "duration_frames": len(history),
                })

        return {
            "primitives": results,
            "is_transition": self._check_transition(results, prev_interaction_graph),
        }

    def _detect_primitive(self, history: List[Dict]) -> tuple:
        """
        Detect primitive from interaction history.
        """
        # Check for REACH: interaction type went from NO_CONTACT/NEAR → TOUCHING
        if self._is_reach(history):
            return Primitive.REACH.value, 0.88

        # Check for GRASP: gesture changed to FIST/GRAB at object
        if self._is_grasp(history):
            return Primitive.GRASP.value, 0.92

        # Check for LIFT: object Y decreasing (in image coords, moving up)
        if self._is_lift(history):
            return Primitive.LIFT.value, 0.85

        # Check for PLACE: object Y increasing (moving down)
        if self._is_place(history):
            return Primitive.PLACE.value, 0.85

        # Check for PUSH: object distance from hand increasing
        if self._is_push(history):
            return Primitive.PUSH.value, 0.80

        # Check for PULL: object distance from hand decreasing
        if self._is_pull(history):
            return Primitive.PULL.value, 0.80

        # Check for TAP: brief contact (< 5 frames)
        if self._is_tap(history):
            return Primitive.TAP.value, 0.78

        return Primitive.IDLE.value, 0.0

    def _is_reach(self, history: List[Dict]) -> bool:
        """Hand moving toward object (distance decreasing)."""
        distances = [h["distance_px"] for h in history]
        if len(distances) < 3:
            return False
        # Distance decreasing over last 5 frames
        recent = distances[-5:]
        if len(recent) < 2:
            return False
        decreasing = all(recent[i] > recent[i+1] for i in range(len(recent)-1))
        return decreasing and recent[-1] < recent[0] * 0.7

    def _is_grasp(self, history: List[Dict]) -> bool:
        """Gesture transitioned to closed hand near object."""
        if len(history) < 3:
            return False
        recent_gestures = [h["hand_gesture"] for h in history[-3:]]
        # Closed hand
        return "FIST" in recent_gestures or "GRAB" in recent_gestures

    def _is_lift(self, history: List[Dict]) -> bool:
        """Object being moved upward."""
        recent = history[-5:]
        return (all(h["interaction_type"] in ("HOLDING", "GRASPING")
                   for h in recent)
                and len(recent) >= 5)

    def _is_place(self, history: List[Dict]) -> bool:
        """Object being placed down."""
        # Detect: was holding, now releasing with downward motion
        if len(history) < 5:
            return False
        was_holding = any(h["interaction_type"] == "HOLDING" for h in history[:-2])
        now_releasing = history[-1]["interaction_type"] == "RELEASING"
        return was_holding and now_releasing

    def _is_push(self, history: List[Dict]) -> bool:
        """Object being pushed away."""
        if len(history) < 3:
            return False
        distances = [h["distance_px"] for h in history[-3:]]
        return distances[-1] > distances[0] * 1.3

    def _is_pull(self, history: List[Dict]) -> bool:
        """Object being pulled closer."""
        if len(history) < 3:
            return False
        distances = [h["distance_px"] for h in history[-3:]]
        return distances[-1] < distances[0] * 0.7

    def _is_tap(self, history: List[Dict]) -> bool:
        """Brief contact (touch and release)."""
        if len(history) < 3 or len(history) > 8:
            return False
        return any(h["interaction_type"] == "TOUCHING" for h in history)

    def _check_transition(self, current, prev) -> bool:
        """Check if a primitive just changed."""
        if not prev:
            return False
        prev_prims = {p["primitive"] for p in prev.get("primitives", [])}
        curr_prims = {p["primitive"] for p in current}
        return prev_prims != curr_prims
