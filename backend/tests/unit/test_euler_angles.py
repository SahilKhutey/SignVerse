"""
Unit tests for Euler angle conversion.
"""
import pytest
import numpy as np
from backend.services.kinematics.euler_angles import bone_to_euler


@pytest.mark.unit
class TestEulerAngles:
    """Tests for bone_to_euler function."""
    
    def test_vertical_orientation(self):
        """Pure downward vector [0, -1, 0] should yield zero rotation."""
        rad, deg = bone_to_euler([0.0, -1.0, 0.0])
        np.testing.assert_allclose(rad, [0.0, 0.0, 0.0], atol=1e-5)
        np.testing.assert_allclose(deg, [0.0, 0.0, 0.0], atol=1e-5)
    
    def test_horizontal_orientation(self):
        """Horizontal vectors should yield 90-degree rotations."""
        # Right [1, 0, 0] -> yaw = 90 deg (or pi/2 rad)
        rad, deg = bone_to_euler([1.0, 0.0, 0.0])
        # rad is [roll, pitch, yaw]. Z is yaw, so rad[2] should be ~1.5708 (pi/2)
        assert deg[2] == pytest.approx(90.0)
        assert deg[0] == pytest.approx(0.0)
        
        # Forward [0, 0, 1] -> pitch = 90 deg
        rad, deg = bone_to_euler([0.0, 0.0, 1.0])
        assert deg[1] == pytest.approx(90.0)
        assert deg[0] == pytest.approx(0.0)
        assert deg[2] == pytest.approx(0.0)
