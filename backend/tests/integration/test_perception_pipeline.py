"""
Integration tests for the perception and motion intelligence pipeline.
"""
import pytest
import numpy as np
from backend.services.perception.holistic_extractor import HolisticExtractor, PerceptionResult, Landmark
from backend.services.motion_fusion.kalman_smoother import TemporalSmoother
from backend.services.perception.interaction import InteractionEngine
from backend.services.motion_intelligence.intent_classifier import IntentClassifier, Intent


@pytest.mark.integration
class TestPerceptionPipelineIntegration:
    """Tests the combined flow of perception, smoothing, HOI, and intent classification."""

    def test_pipeline_flow(self, sample_frame):
        """Should process a frame through extraction, smoothing, interaction, and intent classification."""
        # 1. Initialize components
        extractor = HolisticExtractor()
        smoother = TemporalSmoother()
        interaction_engine = InteractionEngine()
        intent_classifier = IntentClassifier()

        # 2. Extract perception data from dummy BGR frame
        result = extractor.extract(sample_frame, frame_id=1, timestamp_ms=33.3)
        assert isinstance(result, PerceptionResult)

        # 3. Simulate a sequence of frames with a moving hand and a cup
        # Set up synthetic landmarks representing a hand moving towards a cup
        smoother.reset()
        interaction_engine.reset()

        history_results = []
        for frame_idx in range(5):
            # Create a perception result manually
            # Wrist (0) and middle MCP (9)
            wrist_x = 0.5
            wrist_y = 0.6
            
            pose_lms = [Landmark(x=0.5, y=0.5, z=0.0, v=0.9)] * 33
            
            # Left hand landmarks
            left_hand_lms = [Landmark(x=wrist_x, y=wrist_y, z=0.0, v=0.9) for _ in range(21)]
            # Index finger extended (Pointing/Open palm depending on thumb)
            left_hand_lms[0] = Landmark(x=wrist_x, y=wrist_y, z=0.0, v=0.9)
            left_hand_lms[9] = Landmark(x=wrist_x, y=wrist_y - 0.05, z=0.0, v=0.9)
            left_hand_lms[2] = Landmark(x=wrist_x + 0.05, y=wrist_y, z=0.0, v=0.9)
            left_hand_lms[4] = Landmark(x=wrist_x + 0.1, y=wrist_y, z=0.0, v=0.9)
            
            frame_result = PerceptionResult(
                pose=pose_lms,
                left_hand=left_hand_lms,
                right_hand=[],
                face=[],
                confidence_mean=0.9,
                frame_id=frame_idx,
                timestamp_ms=frame_idx * 33.3
            )

            # Smooth landmarks
            smoothed_res = smoother.smooth(frame_result)
            assert len(smoothed_res.left_hand) == 21
            # Verify coordinates are modified/smoothed
            assert smoothed_res.left_hand[0].x > 0.49

            # Run gesture classifier on smoothed landmarks
            left_gesture = extractor.gesture_classifier.classify(smoothed_res.left_hand)
            assert left_gesture in ("OPEN_PALM", "UNKNOWN")

            # Objects in scene
            objects = [{
                "track_id": 1,
                "class": "cup",
                "bbox": [280, 240, 360, 320], # pixel coordinates center ~ 320, 280 (normalized 0.5, 0.58)
                "position_3d": [0.0, 0.0, 0.5],
                "confidence": 0.9
            }]

            # Analyze hand-object interaction
            # Convert normal landmarks back to list of dicts for interaction engine
            left_hand_dicts = [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in smoothed_res.left_hand]
            
            # In image coordinates, width=640, height=480
            # Left hand center is at (wrist_x, wrist_y) normal coordinates, which is around (320, 288)
            # This is very close to bbox center (320, 280)
            graph = interaction_engine.analyze_frame(
                body_landmarks=[{"x": lm.x, "y": lm.y, "z": lm.z} for lm in smoothed_res.pose],
                left_hand=left_hand_dicts,
                right_hand=None,
                left_gesture="FIST",
                right_gesture=None,
                objects=objects,
                gaze={"direction": "center", "target": "cup"}
            )
            
            history_results.append(graph)

        # 4. Final verification of the interaction graph
        last_graph = history_results[-1]
        assert len(last_graph.hand_object_interactions) > 0
        assert last_graph.hand_object_interactions[0].object_class == "cup"
        
        # 5. Classify intent from sequential primitives
        # Let's mock a lift primitive
        primitives = [{"primitive": "LIFT", "confidence": 0.85}]
        
        # Convert interaction graph to dict format expected by IntentClassifier
        graph_dict = interaction_engine.to_dict(last_graph)
        
        intent = intent_classifier.classify(graph_dict, primitives)
        # Should detect DRINK intent because cup is held/near and LIFT primitive is present
        assert intent == Intent.DRINK.value
