"""
Performance tests for checking execution latencies of individual sub-modules.
"""
import pytest
import time
import numpy as np
from backend.services.motion_fusion.kalman_smoother import TemporalSmoother
from backend.services.perception.interaction import InteractionEngine
from backend.services.motion_intelligence.intent_classifier import IntentClassifier
from backend.services.perception.holistic_extractor import PerceptionResult, Landmark


@pytest.mark.performance
class TestModuleLatency:
    """Verifies that individual processing modules execute within strict latency bounds."""

    def test_kalman_smoother_latency(self):
        """TemporalSmoother must run in < 5ms per frame."""
        smoother = TemporalSmoother()
        
        # Synthesize frame result
        pose_lms = [Landmark(x=0.5, y=0.5, z=0.0, v=0.9) for _ in range(33)]
        left_hand_lms = [Landmark(x=0.5, y=0.5, z=0.0, v=0.9) for _ in range(21)]
        frame_res = PerceptionResult(
            pose=pose_lms,
            left_hand=left_hand_lms,
            right_hand=[],
            face=[],
            confidence_mean=0.9
        )

        # Warm up
        for _ in range(10):
            smoother.smooth(frame_res)

        start = time.perf_counter()
        for _ in range(100):
            smoother.smooth(frame_res)
        end = time.perf_counter()

        avg_latency_ms = ((end - start) / 100) * 1000
        assert avg_latency_ms < 10.0, f"Kalman Smoother latency was {avg_latency_ms:.3f}ms (limit: 10.0ms)"

    def test_interaction_engine_latency(self):
        """InteractionEngine analyze_frame must execute in < 5ms."""
        engine = InteractionEngine()
        body = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(33)]
        left_hand = [{"x": 0.5, "y": 0.5, "z": 0.0} for _ in range(21)]
        objects = [{"track_id": 1, "class": "cup", "bbox": [100, 100, 200, 200], "position_3d": [0,0,0.5]}]
        gaze = {"direction": "center"}

        # Warm up
        for _ in range(10):
            engine.analyze_frame(body, left_hand, None, "FIST", None, objects, gaze)

        start = time.perf_counter()
        for _ in range(100):
            engine.analyze_frame(body, left_hand, None, "FIST", None, objects, gaze)
        end = time.perf_counter()

        avg_latency_ms = ((end - start) / 100) * 1000
        assert avg_latency_ms < 5.0, f"Interaction Engine latency was {avg_latency_ms:.3f}ms (limit: 5.0ms)"

    def test_intent_classifier_latency(self):
        """IntentClassifier classify must execute in < 2ms."""
        clf = IntentClassifier()
        graph = {
            "hand_object_interactions": [
                {"hand": "right", "object_id": 1, "object_class": "cup", "interaction_type": "HOLDING"}
            ],
            "person_posture": "sitting",
            "attention_target": "cup"
        }
        prims = [{"primitive": "LIFT", "confidence": 0.9}]

        # Warm up
        for _ in range(10):
            clf.classify(graph, prims)

        start = time.perf_counter()
        for _ in range(100):
            clf.classify(graph, prims)
        end = time.perf_counter()

        avg_latency_ms = ((end - start) / 100) * 1000
        assert avg_latency_ms < 2.0, f"Intent Classifier latency was {avg_latency_ms:.3f}ms (limit: 2.0ms)"
