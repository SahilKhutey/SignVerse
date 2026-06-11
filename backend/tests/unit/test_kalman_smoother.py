"""
Unit tests for Kalman smoother.
"""
import pytest
import numpy as np
from backend.core.kalman_smoother import (
    LandmarkKalman, TemporalSmoother
)


@pytest.mark.unit
class TestLandmarkKalman:
    """Tests for single-landmark Kalman filter."""
    
    def test_initialization(self):
        """Should initialize with default state."""
        kf = LandmarkKalman()
        assert kf.state.shape == (6,)
        assert kf.P.shape == (6, 6)
        assert not kf.initialized
    
    def test_first_measurement_initializes(self):
        """First measurement should initialize state."""
        kf = LandmarkKalman()
        meas = np.array([1.0, 2.0, 3.0])
        result = kf.update(meas)
        np.testing.assert_array_equal(result, meas)
        assert kf.initialized
    
    def test_subsequent_updates_smoothing(self):
        """Subsequent updates should smooth, not jump."""
        kf = LandmarkKalman(measurement_noise=0.5)
        # Initialize at origin
        kf.update(np.array([0.0, 0.0, 0.0]))
        # Add noisy measurement
        noisy = np.array([1.0, 0.0, 0.0])
        result = kf.update(noisy)
        # Should be between 0 and 1 (smoothing effect)
        assert 0.0 < result[0] < 1.0
        assert abs(result[1]) < 0.1
        assert abs(result[2]) < 0.1
    
    def test_normalize_state(self):
        """State should remain bounded."""
        kf = LandmarkKalman()
        for _ in range(10):
            kf.update(np.array([100, 100, 100]))
        assert np.all(np.isfinite(kf.state))


@pytest.mark.unit
class TestTemporalSmoother:
    """Tests for multi-landmark temporal smoother."""
    
    def test_smooth_empty_frame(self):
        """Empty frame should return empty."""
        smoother = TemporalSmoother()
        result = smoother.smooth_frame({
            "pose_33": [],
            "left_hand_21": [],
            "right_hand_21": [],
            "face_468": [],
        })
        assert result["pose_33"] == []
    
    def test_smooth_single_landmark(self):
        """Should smooth a single landmark across groups."""
        smoother = TemporalSmoother()
        result = smoother.smooth_frame({
            "pose_33": [{"x": 1.0, "y": 2.0, "z": 3.0, "v": 0.9}],
            "left_hand_21": [{"x": 4.0, "y": 5.0, "z": 6.0, "v": 0.9}],
            "right_hand_21": [],
            "face_468": [],
        })
        assert len(result["pose_33"]) == 1
        assert len(result["left_hand_21"]) == 1
        assert result["right_hand_21"] == []
    
    def test_reset_clears_state(self):
        """reset() should clear all filters."""
        smoother = TemporalSmoother()
        smoother.smooth_frame({
            "pose_33": [{"x": 1, "y": 2, "z": 3, "v": 0.9}],
            "left_hand_21": [],
            "right_hand_21": [],
            "face_468": [],
        })
        assert len(smoother.filters) > 0
        smoother.reset()
        assert len(smoother.filters) == 0
    
    def test_maintains_separate_filters_per_group(self):
        """Same index in different groups should have separate filters."""
        smoother = TemporalSmoother()
        result = smoother.smooth_frame({
            "pose_33": [{"x": 100, "y": 0, "z": 0, "v": 0.9}],
            "left_hand_21": [{"x": 0, "y": 100, "z": 0, "v": 0.9}],
            "right_hand_21": [],
            "face_468": [],
        })
        # Both groups have index 0, should have separate filters
        assert ("pose", 0) in smoother.filters
        assert ("lh", 0) in smoother.filters
