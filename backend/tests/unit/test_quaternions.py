"""
Unit tests for quaternion conversion.
"""
import pytest
import numpy as np
from backend.services.kinematics.euler_angles import euler_to_quat


@pytest.mark.unit
class TestQuaternions:
    """Tests for euler_to_quat function."""
    
    def test_identity_quaternion(self):
        """Zero rotation should yield identity quaternion [1, 0, 0, 0]."""
        quat = euler_to_quat([0.0, 0.0, 0.0])
        np.testing.assert_allclose(quat, [1.0, 0.0, 0.0, 0.0], atol=1e-5)
    
    def test_quaternion_magnitude(self):
        """Quaternion should always have unit magnitude (norm = 1)."""
        # Test 90 degree pitch
        quat = euler_to_quat([0.0, np.pi/2, 0.0])
        norm = np.linalg.norm(quat)
        assert norm == pytest.approx(1.0)
        
        # Test arbitrary rotation
        quat2 = euler_to_quat([0.1, -0.5, 0.9])
        norm2 = np.linalg.norm(quat2)
        assert norm2 == pytest.approx(1.0)
    
    def test_specific_rotation(self):
        """Verify quaternion components for a known rotation."""
        # 180 degree rotation about Z (yaw) -> [0, 0, 0, 1]
        quat = euler_to_quat([0.0, 0.0, np.pi])
        # [w, x, y, z] -> w = cos(pi/2) = 0, z = sin(pi/2) = 1
        np.testing.assert_allclose(quat, [0.0, 0.0, 0.0, 1.0], atol=1e-5)
