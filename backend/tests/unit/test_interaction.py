"""
Unit tests for human-object interaction engine.
"""
import pytest
from backend.services.perception.interaction import (
    InteractionEngine, InteractionType, InteractionGraph, HandObjectInteraction
)


@pytest.mark.unit
class TestInteractionEngine:
    """Tests for InteractionEngine."""
    
    def test_initialization(self):
        """Engine should initialize with empty state."""
        engine = InteractionEngine()
        assert len(engine.active_interactions) == 0
        assert engine._frame_counter == 0
    
    def test_analyze_frame_empty(self):
        """Should return empty graph if no hands/body present."""
        engine = InteractionEngine()
        graph = engine.analyze_frame(
            body_landmarks=[],
            left_hand=None,
            right_hand=None,
            left_gesture=None,
            right_gesture=None,
            objects=[],
            gaze={"direction": "center", "target": "unknown"}
        )
        assert isinstance(graph, InteractionGraph)
        assert len(graph.hand_object_interactions) == 0
        assert graph.person_posture == "unknown"  # Default posture
    
    def test_find_hand_interactions_near(self):
        """Hand near object should trigger interaction."""
        engine = InteractionEngine()
        
        # Synthetic hand near the object center (75, 75) in pixels
        # Pass normalized coordinates since interaction engine expects them
        nx = 75.0 / 640.0
        ny = 75.0 / 480.0
        hand = [{"x": nx, "y": ny, "z": 0.0} for _ in range(21)]
        # Wrist and MCP positions for palm center estimation
        hand[0] = {"x": nx, "y": ny, "z": 0.0}
        hand[9] = {"x": nx, "y": 80.0 / 480.0, "z": 0.0}
        
        # Tracked cup object near the hand
        objects = [{
            "track_id": 1,
            "class": "cup",
            "bbox": [50, 50, 100, 100],
            "position_3d": [0.0, -0.05, 0.1],  # very close in 3D
            "confidence": 0.9
        }]
        
        graph = engine.analyze_frame(
            body_landmarks=[{"x": 0, "y": 0, "z": 0}] * 33,
            left_hand=hand,
            right_hand=None,
            left_gesture="OPEN_PALM",
            right_gesture=None,
            objects=objects,
            gaze={"direction": "center", "target": "unknown"}
        )
        
        # Should have detected interaction
        assert len(graph.hand_object_interactions) > 0
        interaction = graph.hand_object_interactions[0]
        assert interaction.object_id == 1
        assert interaction.object_class == "cup"
        assert interaction.distance_3d <= 0.35  # D3_NEAR threshold
