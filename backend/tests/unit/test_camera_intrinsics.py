"""
Unit tests for camera intrinsics and estimator.
"""
import pytest
import numpy as np
from backend.services.depth.camera_intrinsics import (
    CameraIntrinsics, CameraIntrinsicsEstimator
)


@pytest.mark.unit
class TestCameraIntrinsics:
    """Tests for CameraIntrinsics class."""
    
    def test_initialization(self):
        """Should initialize correctly and build K matrix."""
        ci = CameraIntrinsics(fx=1000.0, fy=1000.0, cx=640.0, cy=360.0, width=1280, height=720)
        assert ci.fx == 1000.0
        assert ci.fy == 1000.0
        assert ci.cx == 640.0
        assert ci.cy == 360.0
        assert ci.width == 1280
        assert ci.height == 720
        
        K = ci.K
        assert K.shape == (3, 3)
        assert K[0, 0] == 1000.0
        assert K[1, 1] == 1000.0
        assert K[0, 2] == 640.0
        assert K[1, 2] == 360.0
        assert K[2, 2] == 1.0
    
    def test_fov_calculations(self):
        """FOV calculations should match expected trigonometry."""
        ci = CameraIntrinsics(fx=1000.0, fy=1000.0, cx=640.0, cy=360.0, width=1280, height=720)
        # fov_x = 2 * arctan(width / (2 * fx)) = 2 * arctan(1280 / 2000) = 2 * arctan(0.64) ~ 65 degrees
        assert 60.0 < ci.fov_x_deg < 70.0
        assert 35.0 < ci.fov_y_deg < 45.0
    
    def test_projections(self):
        """Project and unproject should be inverse operations."""
        ci = CameraIntrinsics(fx=1000.0, fy=1000.0, cx=640.0, cy=360.0, width=1280, height=720)
        
        xyz = np.array([0.2, -0.1, 2.0])  # camera-relative 3D coordinate
        px, py = ci.project_3d_to_2d(xyz)
        
        # Unproject back to 3D using same depth
        xyz_recovered = ci.unproject_2d_to_3d(px, py, depth_m=2.0)
        
        np.testing.assert_allclose(xyz_recovered, xyz, atol=1e-5)
    
    def test_dict_serialization(self):
        """Should serialize to dict and deserialize back correctly."""
        ci = CameraIntrinsics(fx=1000.0, fy=1000.0, cx=640.0, cy=360.0, width=1280, height=720)
        d = ci.to_dict()
        assert d["fx"] == 1000.0
        assert d["width"] == 1280
        
        ci2 = CameraIntrinsics.from_dict(d)
        assert ci2.fx == ci.fx
        assert ci2.cx == ci.cx
        assert ci2.width == ci.width


@pytest.mark.unit
class TestCameraIntrinsicsEstimator:
    """Tests for CameraIntrinsicsEstimator class."""
    
    def test_defaults(self):
        """Should return default configurations."""
        estimator = CameraIntrinsicsEstimator(1280, 720)
        webcam = estimator.default_webcam()
        phone = estimator.default_phone()
        
        assert isinstance(webcam, CameraIntrinsics)
        assert isinstance(phone, CameraIntrinsics)
        assert webcam.width == 1280
        assert phone.height == 720
