"""
Unit tests for monocular depth estimator.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from backend.services.depth.depth_estimator import DepthEstimator, DepthResult


@pytest.mark.unit
class TestDepthEstimator:
    """Tests for DepthEstimator."""
    
    @patch("backend.services.depth.depth_estimator.DepthEstimator._load_model")
    def test_singleton(self, mock_load):
        """Should return same instance on multiple calls."""
        # Reset singleton instance
        DepthEstimator._instance = None
        
        det1 = DepthEstimator.get_instance()
        det2 = DepthEstimator.get_instance()
        assert det1 is det2
        assert mock_load.call_count == 1
    
    @patch("backend.services.depth.depth_estimator.DepthEstimator._load_model")
    def test_estimate_mocked(self, mock_load, sample_frame):
        """Should return formatted DepthResult on estimate."""
        DepthEstimator._instance = None
        
        det = DepthEstimator.get_instance()
        det.device = "cpu"
        det._primary = {"type": "midas", "model": MagicMock()}
        det._model_name = "MiDaS_small"
        
        # Mock _infer_primary to return a constant depth map
        with patch.object(det, "_infer_primary") as mock_infer:
            h, w = sample_frame.shape[:2]
            mock_infer.return_value = np.ones((h, w), dtype=np.float32) * 0.5
            
            res = det.estimate(sample_frame)
            
            assert isinstance(res, DepthResult)
            assert res.depth_map.shape == (h, w)
            assert res.model_used == "MiDaS_small"
            assert res.inference_time_ms >= 0
            assert res.scale_factor == 1.0
