"""
Unit tests for ObjectDetector3D.
"""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from backend.services.perception.object_detector import ObjectDetector3D


@pytest.mark.unit
class TestObjectDetector3D:
    """Tests for ObjectDetector3D."""
    
    @patch("backend.services.perception.object_detector.YOLO")
    def test_singleton(self, mock_yolo_cls):
        """Should return same instance on multiple calls."""
        # Reset the singleton instance for testing
        ObjectDetector3D._instance = None
        ObjectDetector3D._initialized = False
        
        det1 = ObjectDetector3D()
        det2 = ObjectDetector3D()
        assert det1 is det2
    
    @patch("backend.services.perception.object_detector.YOLO")
    def test_detect_returns_formatted_results(self, mock_yolo_cls, sample_frame):
        """detect() should run track and map output dict fields."""
        # Reset singleton state
        ObjectDetector3D._instance = None
        ObjectDetector3D._initialized = False
        
        # Mock YOLO model track output
        mock_model = MagicMock()
        mock_yolo_cls.return_value = mock_model
        mock_model.names = {0: "cup"}
        
        mock_result = MagicMock()
        mock_box = MagicMock()
        
        # Mock xyxy, conf, cls, id tensors with .cpu().numpy() chain
        # 1 box
        xyxy_tensor = MagicMock()
        xyxy_tensor.cpu.return_value.numpy.return_value.tolist.return_value = [100.0, 120.0, 200.0, 220.0]
        
        conf_tensor = MagicMock()
        conf_tensor.cpu.return_value.__float__.return_value = 0.95
        
        cls_tensor = MagicMock()
        cls_tensor.cpu.return_value.__int__.return_value = 0
        
        id_tensor = MagicMock()
        id_tensor.cpu.return_value.__int__.return_value = 4
        
        mock_box.xyxy = [xyxy_tensor]
        mock_box.conf = [conf_tensor]
        mock_box.cls = [cls_tensor]
        mock_box.id = [id_tensor]
        mock_box.__len__.return_value = 1
        
        mock_result.boxes = mock_box
        mock_model.track.return_value = [mock_result]
        
        detector = ObjectDetector3D()
        results = detector.detect(sample_frame)
        
        assert len(results) == 1
        res = results[0]
        assert res["class"] == "cup"
        assert res["confidence"] == 0.95
        assert res["track_id"] == 4
        assert "position_3d" in res
        assert "depth_m" in res
        assert "velocity_3d" in res
        assert res["age_frames"] >= 1
