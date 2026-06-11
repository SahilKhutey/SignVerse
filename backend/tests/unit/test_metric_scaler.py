"""
Unit tests for metric scale recovery.
"""
import pytest
import numpy as np
from backend.services.depth.metric_scaler import MetricScaleRecovery, ScaleAnchor


class MockLandmark:
    def __init__(self, x, y, z=0.0, visibility=1.0):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


@pytest.mark.unit
class TestMetricScaleRecovery:
    """Tests for MetricScaleRecovery."""
    
    def test_initialization(self):
        """Should initialize with empty stats."""
        recovery = MetricScaleRecovery()
        assert recovery.use_ema is True
        assert recovery.get_stats()["n_frames"] == 0
        assert recovery.get_stability_score() == 100.0
    
    def test_compute_scale_empty(self):
        """Should fallback to default scale 5.0 if no anchors can be computed."""
        recovery = MetricScaleRecovery()
        depth_map = np.ones((480, 640), dtype=np.float32)
        scale, anchors = recovery.compute_scale(depth_map)
        assert scale == 5.0
        assert len(anchors) == 0
    
    def test_compute_scale_with_landmarks(self, sample_landmarks):
        """Should calculate scale factor using pose landmarks and depth map."""
        recovery = MetricScaleRecovery()
        depth_map = np.ones((480, 640), dtype=np.float32) * 0.5  # constant depth
        
        # Convert to MockLandmark objects with normalized coords
        landmarks = []
        for i, lm in enumerate(sample_landmarks):
            x_norm = lm["x"] / 640.0
            y_norm = lm["y"] / 480.0
            if i == 11:
                x_norm = 280.0 / 640.0
                y_norm = 150.0 / 480.0
            elif i == 12:
                x_norm = 360.0 / 640.0
                y_norm = 150.0 / 480.0
            landmarks.append(MockLandmark(x_norm, y_norm, lm["z"], lm.get("v", 0.95)))
        
        scale, anchors = recovery.compute_scale(depth_map, pose_landmarks=landmarks)
        assert scale > 0
        assert len(anchors) > 0
        assert isinstance(anchors, list)
    
    def test_reset(self, sample_landmarks):
        """reset() should clear stats and filters."""
        recovery = MetricScaleRecovery()
        depth_map = np.ones((480, 640), dtype=np.float32) * 0.5
        
        # Convert to MockLandmark objects with normalized coords
        landmarks = []
        for i, lm in enumerate(sample_landmarks):
            x_norm = lm["x"] / 640.0
            y_norm = lm["y"] / 480.0
            if i == 11:
                x_norm = 280.0 / 640.0
                y_norm = 150.0 / 480.0
            elif i == 12:
                x_norm = 360.0 / 640.0
                y_norm = 150.0 / 480.0
            landmarks.append(MockLandmark(x_norm, y_norm, lm["z"], lm.get("v", 0.95)))
        
        recovery.compute_scale(depth_map, pose_landmarks=landmarks)
        assert recovery.get_stats()["n_frames"] > 0
        
        recovery.reset()
        assert recovery.get_stats()["n_frames"] == 0
        assert recovery.get_stability_score() == 100.0
