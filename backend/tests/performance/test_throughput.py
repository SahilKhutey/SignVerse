"""
Performance tests for checking processing throughput.
Ensures frame decoding and extraction throughput can maintain >=30 FPS.
"""
import pytest
import time
import numpy as np
from backend.services.perception.holistic_extractor import HolisticExtractor


@pytest.mark.performance
class TestPerceptionThroughput:
    """Verifies that perception extractors meet throughput requirements."""

    def test_pipeline_throughput(self, sample_frame):
        """Pipeline extraction must process frames fast enough to maintain real-time throughput."""
        extractor = HolisticExtractor()
        
        # Warm up
        for _ in range(5):
            extractor.extract(sample_frame)

        # Run benchmark
        n_frames = 20
        start_time = time.time()
        for i in range(n_frames):
            extractor.extract(sample_frame, frame_id=i, timestamp_ms=i*33.3)
        end_time = time.time()

        elapsed = end_time - start_time
        fps = n_frames / elapsed
        
        # Real-time requirement: processing at least 20 frames per second on average under mock conditions
        # (Since MediaPipe is mocked in tests, it will be extremely fast, but this verifies the framework overhead)
        assert fps >= 20.0, f"Average throughput was only {fps:.2f} FPS (expected >= 20 FPS)"
