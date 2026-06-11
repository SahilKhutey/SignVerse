"""
Unit tests for action primitive detection.
"""
import pytest
from backend.services.motion_intelligence.action_primitives import (
    ActionPrimitiveDetector, Primitive
)


def make_interaction(hand, object_id, object_class, interaction_type, distance, gesture="OPEN_PALM"):
    """Create a synthetic interaction."""
    return {
        "hand": hand,
        "object_id": object_id,
        "object_class": object_class,
        "interaction_type": interaction_type,
        "distance_px": distance,
        "hand_gesture": gesture,
        "confidence": 0.9,
    }


@pytest.mark.unit
class TestActionPrimitiveDetector:
    """Tests for action primitive detection."""
    
    def test_no_interactions_idle(self):
        """No interactions = IDLE."""
        det = ActionPrimitiveDetector()
        result = det.detect({"hand_object_interactions": []})
        assert result["primitives"] == []
    
    def test_grasp_detected(self):
        """FIST gesture near object = GRASP."""
        det = ActionPrimitiveDetector()
        interaction = make_interaction("right", 1, "cup", "NEAR", 50, "FIST")
        
        # Need history to trigger (at least 3 frames)
        det.detect({"hand_object_interactions": [interaction]})
        det.detect({"hand_object_interactions": [interaction]})
        result = det.detect({"hand_object_interactions": [interaction]})
        
        primitives = [p["primitive"] for p in result["primitives"]]
        assert "GRASP" in primitives
    
    def test_lift_detected(self):
        """HOLDING sustained = LIFT."""
        det = ActionPrimitiveDetector()
        interaction = make_interaction("right", 1, "cup", "HOLDING", 30, "OPEN_PALM")
        
        # Need at least 5 frames of history
        for _ in range(4):
            det.detect({"hand_object_interactions": [interaction]})
        result = det.detect({"hand_object_interactions": [interaction]})
        
        primitives = [p["primitive"] for p in result["primitives"]]
        assert "LIFT" in primitives
    
    def test_history_persistence(self):
        """Detector should maintain interaction history."""
        det = ActionPrimitiveDetector()
        interaction = make_interaction("right", 1, "cup", "TOUCHING", 30, "FIST")
        det.detect({"hand_object_interactions": [interaction]})
        assert len(det.interaction_history) > 0
    
    def test_reset_clears_history(self):
        """Should clear history on reset."""
        det = ActionPrimitiveDetector()
        interaction = make_interaction("right", 1, "cup", "TOUCHING", 30, "FIST")
        det.detect({"hand_object_interactions": [interaction]})
        det.interaction_history.clear()
        assert len(det.interaction_history) == 0
