"""
Unit tests for bone vector computations.
"""
import pytest
import numpy as np
from backend.services.kinematics.bone_vectors import compute_bone_vectors


@pytest.mark.unit
class TestBoneVectors:
    """Tests for compute_bone_vectors function."""
    
    def test_empty_pose(self):
        """Should return empty dict if pose is too short."""
        assert compute_bone_vectors([]) == {}
        assert compute_bone_vectors([{"x": 0, "y": 0, "z": 0}] * 10) == {}
    
    def test_bone_vectors_calculation(self):
        """Should calculate correct directions, lengths, and velocities."""
        # Create standard pose with 33 landmarks
        pose = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(33)]
        
        # Set left shoulder (11) and left elbow (13) to create a specific bone vector
        pose[11] = {"x": 0.0, "y": 0.0, "z": 0.0}
        pose[13] = {"x": 0.0, "y": 2.0, "z": 0.0}  # Vector is [0, 2, 0]
        
        pose[12] = {"x": 1.0, "y": 0.0, "z": 0.0}
        pose[14] = {"x": 1.0, "y": 0.0, "z": 0.0}
        
        res = compute_bone_vectors(pose)
        
        assert "l_shoulder" in res
        assert "spine" in res
        assert "neck" in res
        
        l_shoulder = res["l_shoulder"]
        # Direction should be normalized to [0, 1, 0]
        np.testing.assert_allclose(l_shoulder["dir"], [0.0, 1.0, 0.0], atol=1e-5)
        assert l_shoulder["len"] == pytest.approx(2.0)
        assert l_shoulder["vel"] == [0.0, 0.0, 0.0]
    
    def test_temporal_velocity(self):
        """Velocity should be computed correctly relative to prev_vecs."""
        pose = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(33)]
        pose[11] = {"x": 0.0, "y": 0.0, "z": 0.0}
        pose[13] = {"x": 0.0, "y": 1.0, "z": 0.0}  # dir is [0, 1, 0]
        
        prev_vecs = {
            "l_shoulder": {
                "dir": [1.0, 0.0, 0.0],
                "len": 1.0,
                "vel": [0.0, 0.0, 0.0]
            }
        }
        
        res = compute_bone_vectors(pose, prev_vecs)
        # Velocity is current_dir - prev_dir = [0, 1, 0] - [1, 0, 0] = [-1, 1, 0]
        np.testing.assert_allclose(res["l_shoulder"]["vel"], [-1.0, 1.0, 0.0], atol=1e-5)
